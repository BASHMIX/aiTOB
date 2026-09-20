import asyncio
import httpx
import json

async def test_load():
    url = "http://localhost:8000/api/tournaments"
    headers = {
        "Authorization": "Bearer admin",
        "Content-Type": "application/json"
    }
    payload = {
        "slug": "tournament/fnc1ststartgg"
    }
    
    print("Sending POST request to load tournament...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=15)
            print("Response Status Code:", resp.status_code)
            print("Response Text:", resp.text)
        except Exception as e:
            print("Request failed:", e)

if __name__ == "__main__":
    asyncio.run(test_load())
