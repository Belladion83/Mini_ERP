/* =========================================================
   v47.1 - User Login Lockout Migration
   Adds failed login tracking and account lock fields.

   IMPORTANT:
   This script explicitly switches to MiniERPFNB because running
   migrations from SSMS while connected to master/another database
   will cause: Cannot find object dbo.users.

   If your database name is different, change USE [MiniERPFNB].
========================================================= */

USE [MiniERPFNB];
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    RAISERROR(N'Không tìm thấy bảng dbo.users trong database hiện tại: %s. Hãy kiểm tra dropdown database trong SSMS hoặc sửa dòng USE [MiniERPFNB] cho đúng database.', 16, 1, DB_NAME());
    RETURN;
END;
GO

IF COL_LENGTH('dbo.users', 'failed_login_count') IS NULL
BEGIN
    ALTER TABLE dbo.users
    ADD failed_login_count INT NOT NULL CONSTRAINT DF_users_failed_login_count_v47 DEFAULT(0);
END;
GO

IF COL_LENGTH('dbo.users', 'is_locked') IS NULL
BEGIN
    ALTER TABLE dbo.users
    ADD is_locked BIT NOT NULL CONSTRAINT DF_users_is_locked_v47 DEFAULT(0);
END;
GO

IF COL_LENGTH('dbo.users', 'locked_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD locked_at DATETIME2(0) NULL;
END;
GO

IF COL_LENGTH('dbo.users', 'last_failed_login_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD last_failed_login_at DATETIME2(0) NULL;
END;
GO

IF COL_LENGTH('dbo.users', 'last_login_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD last_login_at DATETIME2(0) NULL;
END;
GO

EXEC(N'
UPDATE dbo.users
SET failed_login_count = ISNULL(failed_login_count, 0),
    is_locked = ISNULL(is_locked, 0)
WHERE failed_login_count IS NULL OR is_locked IS NULL;
');
GO

PRINT 'v47.1 user login lockout migration completed on database: ' + DB_NAME();
