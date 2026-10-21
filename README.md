# Sayno's Study (세이노의 서재)

A small, peaceful 3D study you visit in the browser. You write a letter about a worry,
answer a short questionnaire, and get a reply made only of passages from
*세이노의 가르침* (데이원, 2023) with page numbers. There is no Sayno character and
no invented Sayno dialogue.

The flow: write a letter at the desk, pick the closest worry (matched from the letter's
words, no AI), circle yes or no on a short questionnaire, and the open book shows the reply
with this week's mission. Replies go into the drawer, kept only in the visitor's browser,
where a mission can be stamped as done.

Free and non-commercial. Source of all quoted text: 세이노의 가르침 (데이원, 2023),
author email sayno@korea.com.

## Layout

- `blender/build_study.py` builds the study as a low-poly diorama with Blender's
  Python API (about 340 parts, every object one the book mentions) and renders mood
  previews (`dusk`, `night`, `morning`). The same script also runs in a hosted Blender
  (Higgsfield 3D Jutsu) with plain colours.
- `blender/compose_moods.py` puts the transparent renders on paper-coloured
  backgrounds and makes a comparison sheet.
- `blender/study.blend` is the generated scene; open it in Blender to edit by hand.
- `blender/export_glb.py` exports the study to `web/assets/study.glb`, one named mesh per
  clickable object (letter, calendar, desk_papers, bookshelf, drawer, ...). It bakes each
  mesh's surface detail (wood grain, paper, weave) and ambient occlusion into one JPEG with
  Cycles, skipping faces the page's camera can never see, then compresses the geometry with
  glTF-Transform's meshopt (run through `npx`, so it needs Node).
- `web/study.html` is the page: three.js (r170) and GSAP from public CDNs, time-of-day
  lighting over the baked textures, a wall clock on the visitor's time, click an object to
  read its passage.
- `web/data/passages.json` holds the passage for each object in the room.
- `web/data/worries.json` holds the six work worries (questions, findings, verdict rules),
  the 40 quotes behind them with chapter and page, and one weekly mission per principle.
- `tools/check_passages.py <book.txt> web/data/passages.json web/data/worries.json` checks
  every quote word for word and its cited page against the book text (the book itself is not
  in this repository).
- `tools/build_web.py` inlines the model and passages into `dist/study.html` and `dist/index.html`.

## Running

```sh
python3 -m pip install bpy pillow
python3 blender/build_study.py --save blender/study.blend
python3 blender/build_study.py --mood dusk --out renders/hi_dusk.png --samples 96 --res 1600x1200
python3 blender/compose_moods.py renders renders/moods
python3 blender/export_glb.py web/assets/study.glb   # about 10 minutes; --quick to try things
python3 tools/build_web.py   # then open dist/index.html
```
