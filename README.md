# Sayno's Study (세이노의 서재)

A small, peaceful 3D study you visit in the browser. You write a letter about a worry,
answer a short questionnaire, and get a reply made only of passages from
*세이노의 가르침* (데이원, 2023) with page numbers. There is no invented Sayno dialogue: the Sayno figure (see
`blender/characters.py` and `blender/motions.py`) will only ever show passages from the book.

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
- `blender/characters.py` builds two figurines, Sayno and the visitor, as rigid parts on a
  tree of 17 joints (empties), so a pose is a few joint rotations (with a small two-bone
  reach for the hands) and the same joints can carry glTF animations later. It renders a
  character sheet, a face comparison and both figures standing in the study.
  `blender/characters.blend` is the generated scene.
- `blender/build_house.py` grows the study into a small house, at the concept stage: the study
  as built (plus a place to listen to music), a plain waiting room by the front door where the
  visitor writes the letter, and a garage with an old silver two-seater drawn without brand
  marks, shelves of fourteen cubbies for model bicycles, a workbench, the visitor's bicycle, and
  a corner that recalls the rented garage Sayno lived in (a board desk on dog-leash chains, the
  words he wrote on the wall, pp.324-325). It is a cutaway: front walls stop at 0.3 m and the
  walls between rooms at 0.95 m. It renders the whole house or one room (`--view`), with both
  figures. The words on the garage wall need a Korean brush-script font passed as `--font`
  (East Sea Dokdo, SIL OFL, from github.com/google/fonts); it is not in this repository.
  `blender/house.blend` is the generated scene (without the words).
- `blender/motions.py` computes the figures' motion clips (idle, walk, look, nod, sit down,
  sit, stand up, writing in the notebook standing and seated, holding and offering the
  letter) from a few curves per clip with two-bone IK for legs and arms, and exports both
  figures, a chair and every clip to `web/assets/characters.glb` (one glTF animation per
  figure and clip, meshopt-compressed). `--check` renders strips of poses to look at.
- `web/characters.html` is the motion preview: pick a figure and an action, turn the view.
  The page walks and turns the figures itself and plays look and nod on top of any other
  clip.
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
- `tools/build_web.py` inlines the model and passages into `dist/study.html` and `dist/index.html`,
  and the figures into `dist/characters.html` and `dist/characters/index.html`.

## Running

```sh
python3 -m pip install bpy pillow
python3 blender/build_study.py --save blender/study.blend
python3 blender/build_study.py --mood dusk --out renders/hi_dusk.png --samples 96 --res 1600x1200
python3 blender/compose_moods.py renders renders/moods
python3 blender/characters.py --sheet renders/chars/sheet.png --study renders/chars/study.png --close
python3 blender/characters.py --save blender/characters.blend
python3 blender/build_house.py --out renders/house/overview.png --font EastSeaDokdo-Regular.ttf
python3 blender/build_house.py --view garage --out renders/house/garage.png --font EastSeaDokdo-Regular.ttf
python3 blender/build_house.py --save blender/house.blend
python3 blender/motions.py --glb web/assets/characters.glb   # needs Node for glTF-Transform
python3 blender/motions.py --check renders/motions
python3 blender/export_glb.py web/assets/study.glb   # about 10 minutes; --quick to try things
python3 tools/build_web.py   # then open dist/index.html or dist/characters/index.html
```
