rmdir /s /q test_data
update_recipients.py --memory-dir test_data sample_data\recipients2.csv
update_donors.py --memory-dir test_data sample_data\Donors2.csv
donation_match.py --memory-dir test_data

