V38 - Login/Forgot Password UI Update

No SQL migration is required.

Changes:
- Login title changed to "Đăng nhập".
- Removed demo credential hint from login screen.
- Added password show/hide toggle.
- Added forgot password request flow for User Admin only.
- Forgot password flow sends an email to the Admin user's email address with a link to /login?next=/admin/users.
- Non-admin users receive: "Không có quyền truy cập, vui lòng liên hệ Admin."
- Removed "F&B" wording from visible cards/headers in the main UI.

SMTP setup in .env:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=
SMTP_USE_TLS=yes

Important:
- User Admin must have an email in User Admin master data.
- For Gmail, use an App Password instead of your normal Gmail password.

# v43 note: SMTP_FROM can be blank. The app will use the first active User Admin email from User Master Data as sender.
# SMTP_HOST is still required to send email through a mail server.
