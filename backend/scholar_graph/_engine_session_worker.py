"""Private request/response worker; reuse local engines only within one parse job."""
import contextlib
import json
import sys

import _engine_worker as source

_paddle = {}
_create_paddle = source.paddle_engine


def cached_paddle(language):
    if language not in _paddle:
        _paddle[language] = _create_paddle(language)
    return _paddle[language]


source.paddle_engine = cached_paddle

def main():
    for line in sys.stdin.buffer:
        request = json.loads(line)
        identity = request['id']
        try:
            with contextlib.redirect_stdout(sys.stderr):
                if request['mode'] == 'mineru':
                    result = source.mineru_text(request['path'])
                elif request['mode'] == 'ocr':
                    result = source.paddle_text(request['path'], request['language'], request['pages'])
                else:
                    raise ValueError('Unknown local engine')
            response = {'id': identity, 'result': result}
        except Exception:
            response = {'id': identity, 'error': 'local_engine_failed'}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    # MinerU starts render workers using multiprocessing spawn. Importing this
    # module as __mp_main__ must never start another stdin request loop.
    main()
