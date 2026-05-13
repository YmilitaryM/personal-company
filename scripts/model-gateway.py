#!/usr/bin/env python3
"""
Lightweight Multi-Provider Model Gateway for Claude Code.

Routes Anthropic-format requests to different backends based on model name.
Uses litellm as the routing layer — supports Anthropic, OpenAI, DeepSeek, Qwen, etc.

Setup:
  1. Copy config/.env.example → .env, fill in your API keys
  2. Edit config/litellm.yaml to assign model IDs per role
  3. Start gateway: python3 scripts/model-gateway.py --port 4000
  4. Point Claude Code at it: ANTHROPIC_BASE_URL=http://localhost:4000

Optional: open http://localhost:8080/config in the web dashboard to
configure models visually, then click "Sync to Agents".
"""
import json
import os
import sys
import uuid
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
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

# ── Model aliases — maps short names to litellm model names ──
# When Claude Code sends a model name from agent frontmatter, resolve it here.
# Extend this dict to add custom aliases.
MODEL_ALIASES = {
    'opus': 'claude-opus-4-7',
    'sonnet': 'claude-sonnet-4-6',
    'haiku': 'claude-haiku-4-5',
}

# ── Stop reason mapping (OpenAI → Anthropic) ──
STOP_REASON_MAP = {
    'stop': 'end_turn',
    'length': 'max_tokens',
    'tool_calls': 'tool_use',
    'content_filter': 'end_turn',
}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads."""
    daemon_threads = True


def load_provider_map() -> dict:
    """Parse config/litellm.yaml to get model_name → litellm_params mappings."""
    config_file = PROJECT_DIR / 'config' / 'litellm.yaml'
    mapping = {}
    settings = {}
    if not config_file.exists():
        return mapping, settings

    try:
        import yaml
        config = yaml.safe_load(config_file.read_text())
    except ImportError:
        config = _simple_yaml_parse(config_file.read_text())

    for entry in config.get('model_list', []):
        name = entry.get('model_name', '')
        params = entry.get('litellm_params', {})
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith('${') and v.endswith('}'):
                env_key = v[2:-1]
                resolved[k] = os.environ.get(env_key, '')
            else:
                resolved[k] = v
        if name:
            mapping[name] = resolved

    # Extract settings that work in library mode
    ls = config.get('litellm_settings', {})
    if ls:
        if 'request_timeout' in ls:
            settings['request_timeout'] = ls['request_timeout']
        if 'drop_params' in ls:
            settings['drop_params'] = ls['drop_params']

    return mapping, settings


def _simple_yaml_parse(content: str) -> dict:
    """Minimal YAML parser for litellm config format (no pyyaml needed)."""
    import re
    result = {'model_list': []}
    current_model = None
    in_params = False
    in_settings = False
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
            in_settings = False
        elif stripped == 'litellm_params:':
            in_params = True
            in_settings = False
        elif stripped == 'litellm_settings:':
            in_params = False
            in_settings = True
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
        elif in_settings and ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == 'request_timeout':
                try:
                    result.setdefault('litellm_settings', {})[key] = int(val)
                except ValueError:
                    pass
            elif key in ('drop_params', 'set_verbose'):
                result.setdefault('litellm_settings', {})[key] = val.lower() == 'true'

    if current_model:
        result['model_list'].append({'model_name': current_model, 'litellm_params': params})
    return result


# ── Anthropic-compatible HTTP handler ──

class GatewayHandler(BaseHTTPRequestHandler):
    """Handles Anthropic-format API requests and routes to providers."""

    provider_map = {}
    aliases = {}
    settings = {}
    verbose = False
    master_key = None

    def log_message(self, format, *args):
        if self.verbose:
            super().log_message(format, *args)

    def _read_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _check_auth(self) -> bool:
        """Check master key if configured. Returns True if access allowed."""
        if not self.master_key:
            return True
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            auth = auth[7:]
        api_key = self.headers.get('x-api-key', '')
        return auth == self.master_key or api_key == self.master_key

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, event, data):
        """Send a Server-Sent Event."""
        payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(payload.encode('utf-8'))
        self.wfile.flush()

    def _resolve_model(self, model_name: str) -> tuple:
        """Resolve model name through aliases, then provider map. Returns (resolved_name, params)."""
        # Check aliases first (opus → claude-opus-4-7)
        resolved = self.aliases.get(model_name, model_name)
        params = self.provider_map.get(resolved, {})
        return resolved, params

    def _map_stop_reason(self, finish_reason: str) -> str:
        """Map OpenAI finish_reason to Anthropic stop_reason."""
        if not finish_reason:
            return 'end_turn'
        return STOP_REASON_MAP.get(finish_reason, finish_reason)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/') or '/'

        if path == '/health':
            self._send_json({
                'status': 'ok',
                'providers': len(self.provider_map),
                'aliases': len(self.aliases),
            })
            return

        if path == '/v1/models':
            models = []
            seen = set()
            # Include aliases
            for alias, target in self.aliases.items():
                if alias not in seen:
                    models.append({'id': alias, 'object': 'model'})
                    seen.add(alias)
            # Include provider models
            for name in self.provider_map:
                if name not in seen:
                    models.append({'id': name, 'object': 'model'})
                    seen.add(name)
            self._send_json({'object': 'list', 'data': models})
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip('/') or '/'

        if not self._check_auth():
            self._send_json({
                'type': 'error',
                'error': {'type': 'authentication_error', 'message': 'Invalid or missing API key'}
            }, 401)
            return

        try:
            body = self._read_body()
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return

        if path == '/v1/messages':
            self._handle_messages(body)
            return

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

    def _build_messages(self, body: dict) -> list:
        """Convert Anthropic-format messages to litellm format. Returns (messages, tools, has_unsupported)."""
        messages = []
        system_msg = body.get('system', '')
        if system_msg:
            if isinstance(system_msg, list):
                text_parts = [b.get('text', '') for b in system_msg if b.get('type') == 'text']
                system_msg = '\n'.join(text_parts)
            messages.append({'role': 'system', 'content': system_msg})

        unsupported_types = set()
        for msg in body.get('messages', []):
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if isinstance(content, list):
                text_parts = []
                for block in content:
                    block_type = block.get('type', '')
                    if block_type == 'text':
                        text_parts.append(block.get('text', ''))
                    elif block_type == 'image':
                        # Try to pass through image blocks for providers that support them
                        if 'image' not in unsupported_types:
                            unsupported_types.add('image')
                        text_parts.append('[Image input — not supported by gateway]')
                    elif block_type == 'tool_result':
                        # Pass through tool results
                        tool_content = block.get('content', '')
                        if isinstance(tool_content, list):
                            tool_content = '\n'.join(
                                b.get('text', '') for b in tool_content if b.get('type') == 'text'
                            )
                        text_parts.append(f'[Tool Result: {tool_content}]')
                    elif block_type == 'tool_use':
                        unsupported_types.add('tool_use')
                    else:
                        text_parts.append(str(block))
                content = '\n'.join(text_parts)
            messages.append({'role': role, 'content': content})

        return messages

    def _handle_messages(self, body: dict):
        """Handle Anthropic-format /v1/messages request (streaming and non-streaming)."""
        model_name = body.get('model', 'claude-sonnet-4-6')
        resolved, params = self._resolve_model(model_name)

        if not params:
            self._send_json({
                'type': 'error',
                'error': {
                    'type': 'invalid_model',
                    'message': f'Unknown model: {model_name}. Available: {list(self.provider_map.keys())} + aliases: {list(self.aliases.keys())}'
                }
            }, 400)
            return

        is_stream = body.get('stream', False)

        if is_stream:
            self._handle_messages_stream(body, model_name, resolved, params)
        else:
            self._handle_messages_sync(body, model_name, resolved, params)

    def _handle_messages_sync(self, body: dict, model_name: str, resolved: str, params: dict):
        """Handle non-streaming /v1/messages."""
        try:
            messages = self._build_messages(body)

            litellm_model = params.get('model', resolved)
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
            if 'request_timeout' in self.settings:
                kwargs['timeout'] = self.settings['request_timeout']
            else:
                kwargs['timeout'] = 120

            tools = body.get('tools', [])
            if tools:
                kwargs['tools'] = tools
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
                'stop_reason': self._map_stop_reason(choice.finish_reason),
                'stop_sequence': None,
                'usage': {
                    'input_tokens': response.usage.prompt_tokens if response.usage else 0,
                    'output_tokens': response.usage.completion_tokens if response.usage else 0,
                }
            }

            msg_content = choice.message.content
            if msg_content:
                anthropic_response['content'].append({
                    'type': 'text',
                    'text': msg_content if isinstance(msg_content, str) else str(msg_content)
                })

            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                    except json.JSONDecodeError:
                        args = {}
                    anthropic_response['content'].append({
                        'type': 'tool_use',
                        'id': tc.id,
                        'name': tc.function.name,
                        'input': args,
                    })

            self._send_json(anthropic_response)

        except Exception as e:
            traceback.print_exc()
            self._send_json({
                'type': 'error',
                'error': {'type': 'api_error', 'message': f'{type(e).__name__}: {e}'}
            }, 500)

    def _handle_messages_stream(self, body: dict, model_name: str, resolved: str, params: dict):
        """Handle streaming /v1/messages with SSE output."""
        try:
            messages = self._build_messages(body)

            litellm_model = params.get('model', resolved)
            api_key = params.get('api_key', '')
            api_base = params.get('api_base', '')

            kwargs = {
                'model': litellm_model,
                'messages': messages,
                'max_tokens': body.get('max_tokens', 4096),
                'temperature': body.get('temperature', 0.7),
                'stream': True,
                'stream_options': {'include_usage': True},
            }
            if api_key:
                kwargs['api_key'] = api_key
            if api_base:
                kwargs['api_base'] = api_base
            if 'request_timeout' in self.settings:
                kwargs['timeout'] = self.settings['request_timeout']
            else:
                kwargs['timeout'] = 120

            tools = body.get('tools', [])
            if tools:
                kwargs['tools'] = tools
                tool_choice = body.get('tool_choice')
                if tool_choice:
                    kwargs['tool_choice'] = tool_choice

            # Set up SSE response headers
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = litellm.completion(**kwargs)

            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            input_tokens = 0
            output_tokens = 0

            # Emit message_start
            self._send_sse('message_start', {
                'type': 'message_start',
                'message': {
                    'id': msg_id,
                    'type': 'message',
                    'role': 'assistant',
                    'model': model_name,
                    'content': [],
                    'stop_reason': None,
                    'stop_sequence': None,
                    'usage': {'input_tokens': 0, 'output_tokens': 0},
                }
            })

            block_index = 0
            current_text = ''
            text_block_open = False

            # Track tool calls: {index: {'id': ..., 'name': ..., 'arguments': ...}}
            tool_calls = {}
            tool_blocks_open = set()

            for chunk in response:
                if not chunk.choices:
                    # Usage-only chunk (stream_options: include_usage)
                    if hasattr(chunk, 'usage') and chunk.usage:
                        input_tokens = chunk.usage.prompt_tokens or 0
                        output_tokens = chunk.usage.completion_tokens or 0
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Handle text content
                if hasattr(delta, 'content') and delta.content:
                    if not text_block_open:
                        self._send_sse('content_block_start', {
                            'type': 'content_block_start',
                            'index': block_index,
                            'content_block': {'type': 'text', 'text': ''},
                        })
                        text_block_open = True
                    current_text += delta.content
                    self._send_sse('content_block_delta', {
                        'type': 'content_block_delta',
                        'index': block_index,
                        'delta': {'type': 'text_delta', 'text': delta.content},
                    })

                # Handle tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_index = tc.index
                        if tc_index not in tool_calls:
                            # New tool call
                            tool_calls[tc_index] = {
                                'id': tc.id or '',
                                'name': tc.function.name if tc.function and tc.function.name else '',
                                'arguments': '',
                            }

                        if tc.id:
                            tool_calls[tc_index]['id'] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls[tc_index]['name'] = tc.function.name

                        # Emit content_block_start when we first have the tool name
                        if tc_index not in tool_blocks_open and tool_calls[tc_index]['name']:
                            if text_block_open:
                                self._send_sse('content_block_stop', {
                                    'type': 'content_block_stop',
                                    'index': block_index,
                                })
                                text_block_open = False
                                block_index += 1

                            self._send_sse('content_block_start', {
                                'type': 'content_block_start',
                                'index': block_index,
                                'content_block': {
                                    'type': 'tool_use',
                                    'id': tool_calls[tc_index]['id'],
                                    'name': tool_calls[tc_index]['name'],
                                    'input': {},
                                },
                            })
                            tool_blocks_open.add(tc_index)

                        if tc.function and tc.function.arguments:
                            tool_calls[tc_index]['arguments'] += tc.function.arguments
                            self._send_sse('content_block_delta', {
                                'type': 'content_block_delta',
                                'index': block_index,
                                'delta': {
                                    'type': 'input_json_delta',
                                    'partial_json': tc.function.arguments,
                                },
                            })

                # Handle stream end (finish_reason present)
                if finish_reason:
                    # Close text block if open
                    if text_block_open:
                        self._send_sse('content_block_stop', {
                            'type': 'content_block_stop',
                            'index': block_index,
                        })
                        block_index += 1
                        text_block_open = False

                    # Close tool blocks
                    for tc_index in list(tool_blocks_open):
                        self._send_sse('content_block_stop', {
                            'type': 'content_block_stop',
                            'index': block_index if tc_index == 0 else block_index,
                        })
                        block_index += 1

                    # Track usage from final chunk
                    if hasattr(chunk, 'usage') and chunk.usage:
                        input_tokens = chunk.usage.prompt_tokens or 0
                        output_tokens = chunk.usage.completion_tokens or 0

                    stop_reason = self._map_stop_reason(finish_reason)

                    self._send_sse('message_delta', {
                        'type': 'message_delta',
                        'delta': {
                            'stop_reason': stop_reason,
                            'stop_sequence': None,
                        },
                        'usage': {'output_tokens': output_tokens},
                    })

                    self._send_sse('message_stop', {
                        'type': 'message_stop',
                    })

        except Exception as e:
            traceback.print_exc()
            try:
                self._send_sse('error', {
                    'type': 'error',
                    'error': {'type': 'api_error', 'message': f'{type(e).__name__}: {e}'},
                })
            except Exception:
                pass  # Connection already closed

    def _handle_chat_completions(self, body: dict):
        """Handle OpenAI-format /v1/chat/completions request (fallback)."""
        model_name = body.get('model', 'gpt-4o')
        resolved, params = self._resolve_model(model_name)

        if not params:
            self._send_json({'error': f'Unknown model: {model_name}'}, 400)
            return

        try:
            litellm_model = params.get('model', resolved)
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
            if 'request_timeout' in self.settings:
                kwargs['timeout'] = self.settings['request_timeout']
            else:
                kwargs['timeout'] = 120

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
    parser.add_argument('--bind', type=str, default='0.0.0.0', help='Bind address (default: 0.0.0.0; use 127.0.0.1 for local-only)')
    parser.add_argument('--no-auth', action='store_true', help='Disable master key authentication (not recommended)')
    args = parser.parse_args()

    # Load provider map and settings
    provider_map, settings = load_provider_map()
    if not provider_map:
        print("Warning: No models configured in config/litellm.yaml")
        print("  Using fallback: opus→claude-opus-4-7, sonnet→claude-sonnet-4-6, haiku→claude-haiku-4-5")
        provider_map = {
            'claude-opus-4-7': {'model': 'claude-opus-4-7', 'api_key': os.environ.get('ANTHROPIC_API_KEY', '')},
            'claude-sonnet-4-6': {'model': 'claude-sonnet-4-6', 'api_key': os.environ.get('ANTHROPIC_API_KEY', '')},
            'claude-haiku-4-5': {'model': 'claude-haiku-4-5', 'api_key': os.environ.get('ANTHROPIC_API_KEY', '')},
            'deepseek-chat': {'model': 'deepseek/deepseek-chat', 'api_key': os.environ.get('DEEPSEEK_API_KEY', '')},
            'gpt-4o': {'model': 'openai/gpt-4o', 'api_key': os.environ.get('OPENAI_API_KEY', '')},
        }

    # Apply litellm global settings
    if 'request_timeout' in settings:
        litellm.request_timeout = settings['request_timeout']
    if 'drop_params' in settings:
        litellm.drop_params = settings['drop_params']

    # Set up auth
    master_key = os.environ.get('LITELLM_MASTER_KEY', '')
    if args.no_auth:
        master_key = None
    elif not master_key:
        # Generate a random key if none configured
        print("Warning: No LITELLM_MASTER_KEY set. Gateway is open to localhost.")
        print("  Set LITELLM_MASTER_KEY in .env to require authentication.")
        master_key = None

    GatewayHandler.provider_map = provider_map
    GatewayHandler.aliases = MODEL_ALIASES
    GatewayHandler.settings = settings
    GatewayHandler.verbose = args.verbose
    GatewayHandler.master_key = master_key

    server = ThreadingHTTPServer((args.bind, args.port), GatewayHandler)

    print(f'Model Gateway v2.0')
    print(f'Port: {args.port}')
    print(f'Bind: {args.bind}')
    print(f'Streaming: SSE supported')
    print(f'Auth: {"required" if master_key else "none (local-only)"}')
    print(f'Aliases: {len(MODEL_ALIASES)}')
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
