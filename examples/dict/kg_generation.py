from __future__ import annotations

import json
import tempfile
from pathlib import Path

import worph


users_dict = {
    "users": [
        {"id": 1, "username": "@jude", "name": "Jude", "surname": "White"},
        {"id": 2, "username": "@emily", "name": "Emily", "surname": "Van de Beeck"},
        {"id": 3, "username": "@wayne", "name": "Wayne", "surname": "Peterson"},
        {"id": 4, "username": "@jordan1", "name": "Jordan", "surname": "Stones"},
    ]
}

followers_dict = {
    "followers": [
        {"id": 1, "follows": [2, 3], "followed_by": 2},
        {"id": 2, "follows": [3, 5], "followed_by": [1, 3, 4, 5]},
        {"id": 3, "follows": [1, 2], "followed_by": 1},
        {"id": 4, "follows": [1, 2, 3], "followed_by": [2, 3]},
    ]
}

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    users_json = tmp / "users.json"
    followers_json = tmp / "followers.json"
    mapping_path = tmp / "mapping.yml"

    users_json.write_text(json.dumps(users_dict), encoding="utf-8")
    followers_json.write_text(json.dumps(followers_dict), encoding="utf-8")

    mapping_path.write_text(
        """
prefixes:
  insta: http://instagram.com/data/
  rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#

mappings:
  people:
    sources:
      - [users.json~jsonpath, "$.users[*]"]
    s: http://instagram.com/data/user$(id)
    po:
      - [a, insta:User]
      - [insta:username, $(username)]
      - [insta:name, $(name) $(surname)]

  follows:
    sources:
      - [followers.json~jsonpath, "$.followers[*]"]
    s: http://instagram.com/data/user$(id)
    po:
      - [insta:follows, http://instagram.com/data/user$(follows)~iri]
""".strip(),
        encoding="utf-8",
    )

    config = f"[DataSource1]\nmappings={mapping_path.as_posix()}\n"
    graph = worph.materialize(config)

print("Knowledge graph triples:")
for s, p, o in graph.triples((None, None, None)):
    print(s, p, o)
