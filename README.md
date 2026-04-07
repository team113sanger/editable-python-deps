# editable-python-deps
A development environment utility script that lets a user reproducibly switch specfied Python dependencies from non-editable to user-editable git clones. This is to streamline the git flow when writing intragration code that spans two related code bases.


## Concept

```
BEFORE                                  AFTER
 ------                                  -----

 Edit library                              Edit library
      |                                       |
      ▼                                       ▼
 Commit, tag, push                         Test --► Broken? Or a new feature
      |                                       |
      ▼                                       ▼
 Wait ~20 min for CI...                    Just fix it
      |                                       |
      ▼                                       ▼
 poetry update --► Integrate --► Broken?   Confident it works
                              |               |
                              ▼               ▼
                           Start over      Commit, tag, push
```
