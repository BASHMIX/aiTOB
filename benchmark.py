import timeit
import time
from typing import Set

class MockWebSocket:
    pass

subscriptions = {f"slug_{i}": {MockWebSocket(), MockWebSocket()} for i in range(1000)}
target_ws = MockWebSocket()
for i in range(500):
    subscriptions[f"slug_{i}"].add(target_ws)

def test_original():
    subs = {k: v.copy() for k, v in subscriptions.items()}
    # Remove from all subscriptions
    for slug in list(subs.keys()):
        if target_ws in subs[slug]:
            subs[slug].remove(target_ws)

def test_list_keys():
    subs = {k: v.copy() for k, v in subscriptions.items()}
    for slug in list(subs):
        if target_ws in subs[slug]:
            subs[slug].remove(target_ws)

def test_no_list():
    subs = {k: v.copy() for k, v in subscriptions.items()}
    for websockets in subs.values():
        if target_ws in websockets:
            websockets.remove(target_ws)

def test_discard():
    subs = {k: v.copy() for k, v in subscriptions.items()}
    for websockets in subs.values():
        websockets.discard(target_ws)

print("Original:", timeit.timeit(test_original, number=10000))
print("List Keys:", timeit.timeit(test_list_keys, number=10000))
print("No List:", timeit.timeit(test_no_list, number=10000))
print("Discard:", timeit.timeit(test_discard, number=10000))
