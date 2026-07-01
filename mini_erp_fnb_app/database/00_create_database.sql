/*
Create database for Mini ERP F&B.
Run this file first in SQL Server Management Studio.
*/

IF DB_ID(N'MiniERPFNB') IS NULL
BEGIN
    CREATE DATABASE MiniERPFNB;
END
GO

USE MiniERPFNB;
GO
