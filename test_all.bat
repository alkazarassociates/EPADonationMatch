pycodestyle donation_data.py
pycodestyle donation_match.py
pycodestyle update_donors.py
pycodestyle update_recipients.py
pycodestyle unit_test.py

mypy donation_data.py
mypy donation_match.py
mypy update_donors.py
mypy update_recipients.py
mypy unit_test.py

python unit_test.py

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

