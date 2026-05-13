#!/usr/bin/env python3
"""
Lightweight Multi-Provider Model Gateway for Claude Code.

Routes Anthropic-format requests to different backends based on model name.
Uses litellm as the routing layer — supports Anthropic, OpenAI, DeepSeek, Qwen, etc.

Setup:
  1. Copy config/.env.example → .env, fill in your API keys
  2. Edit config/models.json to assign model IDs per role
  3. Start gateway: python3 scripts/model-gateway.py --port 4000
  4. Point Claude Code at it: ANTHROPIC_BASE_URL=http://localhost:4000

Optional: open http://localhost:8080/config in the web dashboard to
configure models visually, then click "Sync to Agents".
"""
import json
import os
import sys
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import socketserver
socketserver.TCPServer.allow_reuse_address = True

# Load .env before litellm import so it picks up API keys
PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', Path.cwd()))
ENV_FILE = PROJECT_DIR / '.env'
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# Requires: pip install litellm
try:
    import litellm
except ImportError:
    print("LiteLLM not installed. Run: pip install litellm")
    sys.exit(1)

# ── Provider mapping from litellm.yaml ──

def load_provider_map() -> dict:
    """Parse config/litellm.yaml to get model_name → litellm_params mappings."""
    config_file = PROJECT_DIR / 'config' / 'litellm.yaml'
    mapping = {}
    if not config_file.exists():
        return mapping

    # Simple YAML parser for the litellm config format (avoids pyyaml dependency)
    # litellm itself can parse YAML, but we use a simple approach
    try:
        import yaml
        config = yaml.safe_load(config_file.read_text())
    except ImportError:
        config = _simple_yaml_parse(config_file.read_text())

    for entry in config.get('model_list', []):
        name = entry.get('model_name', '')
        params = entry.get('litellm_params', {})
        # Resolve env vars in params
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith('${') and v.endswith('}'):
                env_key = v[2:-1]
                resolved[k] = os.environ.get(env_key, '')
            else:
                resolved[k] = v
        if name:
            mapping[name] = resolved
    return mapping


def _simple_yaml_parse(content: str) -> dict:
    """Minimal YAML parser for litellm config format (no pyyaml needed)."""
    import re
    result = {'model_list': []}
    current_model = None
    in_params = False
    params = {}

    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if stripped.startswith('model_name:'):
            if current_model:
                result['model_list'].append({'model_name': current_model, 'litellm_params': params})
            current_model = stripped.split(':', 1)[1].strip()
            params = {}
            in_params = False
        elif stripped == 'litellm_params:':
            in_params = True
        elif in_params and ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ('model', 'api_key', 'api_base'):
                params[key] = val
            elif key == 'rpm':
                try:
                    params[key] = int(val)
                except ValueError:
                    pass

    if current_model:
        result['model_list'].append({'model_name': current_model, 'litellm_params': params})
    return result


# ── Anthropic-compatible HTTP handler ──

class GatewayHandler(BaseHTTPRequestHandler):
    """Handles Anthropic-format API requests and routes to providers."""

    provider_map = {}
    verbose = False

    def log_message(self, format, *args):
        if self.verbose:
            super().log_message(format, *args)

    def _read_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _resolve_model(self, model_name: str) -> dict:
        """Look up provider params for a model name."""
        return self.provider_map.get(model_name, {})

    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/') or '/'

        if path == '/health':
            self._send_json({'status': 'ok', 'providers': len(self.provider_map)})
            return

        if path == '/v1/models':
            models = [{'id': name, 'object': 'model'} for name in self.provider_map]
            self._send_json({'object': 'list', 'data': models})
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip('/') or '/'

        try:
            body = self._read_body()
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return

        # Anthropic messages endpoint: /v1/messages
        if path == '/v1/messages':
            self._handle_messages(body)
            return

        # OpenAI chat completions (for compatibility)
        if path == '/v1/chat/completions':
            self._handle_chat_completions(body)
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key, anthropic-version')
        self.end_headers()

    def _handle_messages(self, body: dict):
        """Handle Anthropic-format /v1/messages request."""
        model_name = body.get('model', 'claude-sonnet-4-6')
        params = self._resolve_model(model_name)

        if not params:
            self._send_json({
                'type': 'error',
                'error': {'type': 'invalid_model', 'message': f'Unknown model: {model_name}. Configured models: {list(self.provider_map.keys())}'}
            }, 400)
            return

        try:
            # Map Anthropic format → litellm
            messages = []
            system_msg = body.get('system', '')
            if system_msg:
                messages.append({'role': 'system', 'content': system_msg})
            for msg in body.get('messages', []):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                # Handle content arrays (text + image blocks)
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if block.get('type') == 'text':
                            text_parts.append(block.get('text', ''))
                        # Skip image blocks for non-Anthropic providers
                    content = '\n'.join(text_parts)
                messages.append({'role': role, 'content': content})

            litellm_model = params.get('model', model_name)
            api_key = params.get('api_key', '')
            api_base = params.get('api_base', '')

            kwargs = {
                'model': litellm_model,
                'messages': messages,
                'max_tokens': body.get('max_tokens', 4096),
                'temperature': body.get('temperature', 0.7),
            }
            if api_key:
                kwargs['api_key'] = api_key
            if api_base:
                kwargs['api_base'] = api_base

            # Check for tools
            tools = body.get('tools', [])
            if tools:
                kwargs['tools'] = tools
                # Only pass tool_choice if tools are present
                tool_choice = body.get('tool_choice')
                if tool_choice:
                    kwargs['tool_choice'] = tool_choice

            response = litellm.completion(**kwargs)
            choice = response.choices[0]

            # Convert to Anthropic response format
            anthropic_response = {
                'id': f'msg_{response.id}',
                'type': 'message',
                'role': 'assistant',
                'model': model_name,
                'content': [],
                'stop_reason': choice.finish_reason or 'end_turn',
                'stop_sequence': None,
                'usage': {
                    'input_tokens': response.usage.prompt_tokens if response.usage else 0,
                    'output_tokens': response.usage.completion_tokens if response.usage else 0,
                }
            }

            # Map content
            msg_content = choice.message.content
            if msg_content:
                anthropic_response['content'].append({
                    'type': 'text',
                    'text': msg_content if isinstance(msg_content, str) else str(msg_content)
                })

            # Map tool calls
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    anthropic_response['content'].append({
                        'type': 'tool_use',
                        'id': tc.id,
                        'name': tc.function.name,
                        'input': json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                    })

            self._send_json(anthropic_response)

        except Exception as e:
            traceback.print_exc()
            self._send_json({
                'type': 'error',
                'error': {'type': 'api_error', 'message': f'{type(e).__name__}: {e}'}
            }, 500)

    def _handle_chat_completions(self, body: dict):
        """Handle OpenAI-format /v1/chat/completions request (fallback)."""
        model_name = body.get('model', 'gpt-4o')
        params = self._resolve_model(model_name)

        if not params:
            self._send_json({'error': f'Unknown model: {model_name}'}, 400)
            return

        try:
            litellm_model = params.get('model', model_name)
            kwargs = {
                'model': litellm_model,
                'messages': body.get('messages', []),
                'max_tokens': body.get('max_tokens', 4096),
                'temperature': body.get('temperature', 0.7),
            }
            api_key = params.get('api_key', '')
            api_base = params.get('api_base', '')
            if api_key:
                kwargs['api_key'] = api_key
            if api_base:
                kwargs['api_base'] = api_base

            response = litellm.completion(**kwargs)
            choice = response.choices[0]

            openai_response = {
                'id': response.id,
                'object': 'chat.completion',
                'model': model_name,
                'choices': [{
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': choice.message.content or ''
                    },
                    'finish_reason': choice.finish_reason or 'stop'
                }],
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                    'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                    'total_tokens': response.usage.total_tokens if response.usage else 0,
                }
            }
            self._send_json(openai_response)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)


def main():
    parser = argparse.ArgumentParser(description='AI Dev Team Model Gateway')
    parser.add_argument('--port', type=int, default=4000, help='Gateway port (default: 4000)')
    parser.add_argument('--verbose', action='store_true', help='Enable request logging')
    args = parser.parse_args()

    # Load provider map
    provider_map = load_provider_map()
    if not provider_map:
        print("⚠ No models configured in config/litellm.yaml")
        print("  Using fallback: all models route through litellm default")
        provider_map = {
            'deepseek-chat': {'model': 'deepseek/deepseek-chat', 'api_key': os.environ.get('DEEPSEEK_API_KEY', '')},
            'gpt-4o': {'model': 'openai/gpt-4o', 'api_key': os.environ.get('OPENAI_API_KEY', '')},
        }

    GatewayHandler.provider_map = provider_map
    GatewayHandler.verbose = args.verbose

    server = HTTPServer(('0.0.0.0', args.port), GatewayHandler)

    print(f'Model Gateway v1.0')
    print(f'Port: {args.port}')
    print(f'Providers: {len(provider_map)}')
    for name, params in provider_map.items():
        has_key = '***' if params.get('api_key') else 'MISSING'
        print(f'  {name} → {params.get("model", "?")} (key: {has_key})')
    print(f'')
    print(f'Claude Code env:')
    print(f'  export ANTHROPIC_BASE_URL=http://localhost:{args.port}')
    print(f'')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.')
        server.shutdown()


if __name__ == '__main__':
    main()
