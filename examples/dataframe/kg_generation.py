from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import worph


users_df = pd.DataFrame(
    {
        "Id": [1, 2, 3, 4],
        "Username": ["@jude", "@emily", "@wayne", "@jordan1"],
        "Name": ["Jude", "Emily", "Wayne", "Jordan"],
        "Surname": ["White", "Van de Beeck", "Peterson", "Stones"],
    }
)

followers_df = pd.DataFrame(
    {
        "Id": [1, 2, 3, 4],
        "Followers": [344, 456, 1221, 23],
    }
)

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    users_csv = tmp / "users.csv"
    followers_csv = tmp / "followers.csv"
    mapping_path = tmp / "mapping.yml"

    users_df.to_csv(users_csv, index=False)
    followers_df.to_csv(followers_csv, index=False)

    mapping_path.write_text(
        """
prefixes:
  insta: http://instagram.com/data/
  rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#

mappings:
  people:
    sources:
      - [users.csv~csv]
    s: http://instagram.com/data/user$(Id)
    po:
      - [a, insta:User]
      - [insta:username, $(Username)]
      - [insta:name, $(Name) $(Surname)]

  followers:
    sources:
      - [followers.csv~csv]
    s: http://instagram.com/data/user$(Id)
    po:
      - [insta:followersNumber, $(Followers)]
""".strip(),
        encoding="utf-8",
    )

    config = f"[DataSource1]\nmappings={mapping_path.as_posix()}\n"
    graph = worph.materialize(config)

print("Knowledge graph triples:")
for s, p, o in graph.triples((None, None, None)):
    print(s, p, o)
