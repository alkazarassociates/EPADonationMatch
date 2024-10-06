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
#echo Skip long run
#goto Success


@echo Testing sample data
@del /q test_data\*
update_donors.py sample_data\dw1.csv --memory-dir test_data
update_recipients.py sample_data\rw1.csv --memory-dir test_data
donation_match.py --memory-dir test_data
@echo ----
update_donors.py sample_data\dw2.csv --memory-dir test_data
update_recipients.py sample_data\rw2.csv --memory-dir test_data
donation_match.py --memory-dir test_data
@echo ----
update_donors.py sample_data\dw3.csv --memory-dir test_data
update_recipients.py sample_data\rw3.csv --memory-dir test_data
donation_match.py --memory-dir test_data

@goto Success
:Failure
@Echo ------- FAILURE ----------
:Success

