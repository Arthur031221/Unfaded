# Example photos

These four photographs are used by the benchmark, the tests and the live demo. All of them come from Wikimedia Commons, where each one is marked as public domain or as having no known copyright restrictions. Two of them were downscaled by the source site before I got them. I did not edit them.

| File | Commons page | Status on Commons |
| --- | --- | --- |
| `roy-family-1891.jpg` | https://commons.wikimedia.org/wiki/File:Andrew_Roy_Family_1891.jpg | Public domain |
| `king-family.jpg` | https://commons.wikimedia.org/wiki/File:Thomas_James_King_and_family_(PP-74-9-020).jpg | Public domain |
| `clemons-logging-camp-1926.jpg` | https://commons.wikimedia.org/wiki/File:Family_group_at_Clemons_Logging_Company_camp_no_5,_1926_(KINSEY_102).jpg | Public domain |
| `knowles-family-portrait.jpg` | https://commons.wikimedia.org/wiki/File:Family_portrait,_parents_with_three_children._Original_glass_plate_negative_is_from_the_J._C._Knowles_Collection,_PhC.182,_State_Archives_of_North_Carolina._(8720643985).jpg | No restrictions (State Archives of North Carolina) |

They are old scans, so they carry their own grain and damage. The benchmark treats each one as the clean reference and adds known damage on top, which is why the numbers measure repair of the added damage and not of the original wear.

## examples/scans

`album-damaged.jpg`, `creased-damaged.jpg` and `camp-damaged.jpg` are made from the photos above by `scripts/make_demo.py`. They add synthetic scratches, a crease and dust with fixed seeds, and `album-damaged.jpg` places four prints on a flatbed background. They are derived works of public domain scans, meant for trying the tool.
