pycodestyle donation_data.py
@if ERRORLEVEL 1 goto Failure
pycodestyle donation_match.py
@if ERRORLEVEL 1 goto Failure
pycodestyle update_donors.py
@if ERRORLEVEL 1 goto Failure
pycodestyle update_recipients.py
@if ERRORLEVEL 1 goto Failure
pycodestyle unit_test.py
@if ERRORLEVEL 1 goto Failure

mypy donation_data.py
@if ERRORLEVEL 1 goto Failure
mypy donation_match.py
@if ERRORLEVEL 1 goto Failure
mypy update_donors.py
@if ERRORLEVEL 1 goto Failure
mypy update_recipients.py
@if ERRORLEVEL 1 goto Failure
mypy unit_test.py
@if ERRORLEVEL 1 goto Failure

python unit_test.py
@if ERRORLEVEL 1 goto Failure
rem echo Skip long run
rem goto Success


@echo Testing sample data
@del /q test_data\*
update_donors.py sample_data\dw1.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
update_recipients.py sample_data\rw1.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
donation_match.py --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
@echo ----
update_donors.py sample_data\dw2.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
rem This has a duplicate home email, and should fail.
update_recipients.py sample_data\rw2_dups.csv --memory-dir test_data
@if NOT ERRORLEVEL 1 goto Failure
@echo The above error was expected!
update_recipients.py sample_data\rw2.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
donation_match.py --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
@echo ----
update_donors.py sample_data\dw3.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
rem This has duplicate home emails, and should fail.
update_recipients.py sample_data\rw3_dups.csv --memory-dir test_data
@if NOT ERRORLEVEL 1 goto Failure
@echo The above error was expected!
update_recipients.py sample_data\rw3.csv --memory-dir test_data
@if ERRORLEVEL 1 goto Failure
donation_match.py --memory-dir test_data
@if ERRORLEVEL 1 goto Failure

@goto Success
:Failure
@Echo ------- FAILURE ----------
:Success

