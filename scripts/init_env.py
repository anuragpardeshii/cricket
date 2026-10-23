from pathlib import Path
import os
import secrets
path=Path('.env')
if not path.exists():
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(f'POSTGRES_PASSWORD={secrets.token_hex(32)}\nTEST_POSTGRES_PASSWORD={secrets.token_hex(32)}\nAPP_DATABASE_PASSWORD={secrets.token_hex(32)}\n')
    print('Created local .env with generated database credentials.')
else: print('Using existing .env.')
