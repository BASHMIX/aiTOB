import asyncio
from backend.core.startgg_client import StartGGClient

async def main():
    sgg = StartGGClient()
    sets = await sgg.fetch_tournament_sets("fnc1ststartgg")
    types = set()
    for s in sets:
        # Since slots are deleted in fetch_tournament_sets, I'll check p1_avatar and p2_avatar
        pass
    
    # Let's do a raw query instead
    query = """
    query TournamentSets($slug: String!) {
      tournament(slug: $slug) {
        events {
          sets(page: 1, perPage: 50) {
            nodes {
              slots {
                entrant {
                  participants {
                    user {
                      images {
                        type
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    data = await sgg.query(query, {"slug": "fnc1ststartgg"})
    for event in data["tournament"]["events"]:
        for s in event["sets"]["nodes"]:
            for slot in s["slots"]:
                if slot.get("entrant"):
                    for p in slot["entrant"].get("participants", []):
                        if p.get("user"):
                            for img in p["user"].get("images", []):
                                types.add(img.get("type"))
    print(f"Found image types: {types}")

if __name__ == "__main__":
    asyncio.run(main())
