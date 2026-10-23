"""Explicit operator-only admin grant; never trusts self-registered email for promotion."""
import argparse
from sqlalchemy import select
from .db import Session,User,Audit

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('email'); args=parser.parse_args()
    with Session.begin() as session:
        user=session.scalar(select(User).where(User.email==args.email.lower(),User.is_guest.is_(False)).with_for_update())
        if not user: raise SystemExit('Account does not exist. Register first, then rerun this operator command.')
        user.is_admin=True; session.add(Audit(action='admin.granted',actor=user.id))
    print('Administrator role granted to the existing account.')
if __name__=='__main__': main()
