$ErrorActionPreference = "Stop"

Write-Host "Starting Smart Rehabilitation IoT demo services..."
Write-Host "Make sure Mosquitto is running on localhost:1883 first."

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m catalog.system_catalog --config configs/catalog.json"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m adapter.thingspeak_adapter --config configs/thingspeak.json"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m control.vital_signs_controller --config configs/controllers.json"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m control.activity_controller --config configs/controllers.json"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m control.sleep_controller --config configs/controllers.json"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m control.medication_controller --config configs/controllers.json"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m control.reminder_scheduler --config configs/controllers.json"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m dashboard.dashboard_backend --config configs/dashboard.json"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..'; python -m connector.raspberry_pi_connector --config configs/raspberry_pi_connector.json"

Write-Host "Dashboard: http://127.0.0.1:8093"
