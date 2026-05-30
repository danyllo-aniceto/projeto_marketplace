@echo off
"C:\Users\danyl\AppData\Local\Programs\Python\Python314\python.exe" manage.py test marketplace_app.tests_trade_flow.TradeFlowTests.test_proposal_image_upload_and_delivery_flow -v 3 --keepdb --failfast > test_run_log.txt 2>&1
exit /b %ERRORLEVEL%