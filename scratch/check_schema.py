import httpx
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("STARTGG_API_TOKEN")

query = """
{
  __schema {
    mutationType {
      fields {
        name
      }
    }
  }
}
"""

def check():
    resp = httpx.post("https://api.start.gg/gql/alpha", 
                      json={"query": query}, 
                      headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200:
        data = resp.json()
        fields = data.get("data", {}).get("__schema", {}).get("mutationType", {}).get("fields", [])
        names = [f["name"] for f in fields]
        print("Valid Mutations:")
        for name in sorted(names):
            if any(x in name.lower() for x in ["set", "dq", "disq", "entrant"]):
                print(f"  - {name}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    check()
