#!/bin/bash

# Test API endpoint with curl
API_URL="https://integration.iqright.app/api/apiGetUserInfo"

echo "Testing API connectivity with curl..."
echo "URL: $API_URL"
echo ""

# First test: Simple connectivity check (no auth)
echo "1. Testing basic connectivity (expecting 401 Unauthorized):"
curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "accept: application/json" \
  -H "caller: LocalApp" \
  -H "idFacility: 1" \
  -d '{"searchCode": "TEST123"}' \
  -w "\nHTTP Status: %{http_code}\nTime Total: %{time_total}s\n" \
  -m 10

echo ""
echo "2. Testing with authentication (replace USERNAME and PASSWORD):"
echo "Run: curl -X POST \"$API_URL\" \\"
echo "  -u IQRightAppUser:IQR1ght!nt3gr4t10n \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"accept: application/json\" \\"
echo "  -H \"caller: LocalApp\" \\"
echo "  -H \"idFacility: 1\" \\"
echo "  -d '{\"searchCode\": \"TEST123\"}' \\"
echo "  -w \"\\nHTTP Status: %{http_code}\\nTime Total: %{time_total}s\\n\" \\"
echo "  -m 10"