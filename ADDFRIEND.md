# Adding Friends to Tulip

Email is not configured on this server, so we bypass all email verification.

## Quick Add a Friend

SSH into the server and run:

```bash
ssh spwplace.fg-goose.online "sudo -u zulip /home/zulip/deployments/current/manage.py shell" << 'PYTHON'
from zerver.models import Realm, UserProfile
from zerver.actions.create_user import do_create_user

realm = Realm.objects.exclude(string_id='zulipinternal').first()

user = do_create_user(
    email="friend@example.com",
    password="temppassword123",
    realm=realm,
    full_name="Friend Name",
    acting_user=None,
)

print(f"✅ Created: {user.delivery_email} / temppassword123")
print(f"🌐 Login at: {realm.url}")
PYTHON
```

## Set Password for Existing User

If someone already has an account but needs a password reset:

```bash
ssh spwplace.fg-goose.online "sudo -u zulip /home/zulip/deployments/current/manage.py shell" << 'PYTHON'
from zerver.models import UserProfile
from django.contrib.auth.hashers import make_password

# Change this to the user's email
user = UserProfile.objects.get(delivery_email="cubelocked@gmail.com")

user.password = make_password("newpassword123")
user.save()

print(f"✅ Password updated for: {user.delivery_email}")
print(f"🔑 New password: newpassword123")
PYTHON
```

## Current Settings

- **Signup Mode**: Invite-only ✅
- **Email Verification**: Bypassed (AUTO_VERIFY_EMAIL_ADDRESSES=True) ✅
- **Confirmation Links**: Never expire ✅

## Example Users Created

- **cubelocked@gmail.com** / `clankerville123`
  - Created: 2026-02-03
  - Login: https://tulip.fg-goose.online
