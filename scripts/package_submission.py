import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root.parent / '23231203-陈佩-23211256-赵浩然-FiberScope.zip'
excluded = {'.git', '__pycache__', '.runtime', '.venv', 'tmp'}
files = [p for p in root.rglob('*') if p.is_file() and not any(part in excluded for part in p.relative_to(root).parts) and p.name != '.env' and p.suffix not in ('.pyc','.gguf','.exe','.dll')]
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, '23231203-陈佩-23211256-赵浩然-FiberScope/' + path.relative_to(root).as_posix())
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert any(n.endswith('/report.pdf') for n in archive.namelist())
print(target)
print(f'{len(files)} files, {target.stat().st_size} bytes; ZIP integrity passed')
