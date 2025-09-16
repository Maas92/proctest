CREATE OR ALTER PROCEDURE dbo.usp_test
AS
BEGIN
    select 'hello from test one' as column1, 'this is another column for testing' as column2
    , 'I made more changes to test git' as column3, 'even more changes' as column4, 'final change' as column5
END;