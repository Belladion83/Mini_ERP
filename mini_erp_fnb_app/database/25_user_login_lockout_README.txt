v47 - User Login Lockout

Run this migration in SSMS:

database/25_user_login_lockout_migration.sql

Features:
- Wrong password increments failed_login_count.
- User is locked at 5 failed attempts.
- Successful login before lock resets failed_login_count to 0.
- Admin can unlock user from User Admin -> Edit User by unticking Account Lock and saving.
