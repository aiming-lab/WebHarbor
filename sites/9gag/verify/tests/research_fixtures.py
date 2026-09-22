"""Independent multi-source answer fixtures; never supplied to the browser driver."""

ANSWERS = {
    0: "The ocean-view lighthouse office is 4.2 meters wide with a reclaimed oak desk. The bookshop model has a pine and brass reading desk. At the remote lighthouse, a radio operator tested new equipment during a winter storm.",
    1: "Miso, the rescue cat, arrived in February and learned the treat-drawer routine in eleven days. Basil, the rescue dog, recognized and greeted the volunteer at the spring open house. Juniper, the foster kitten, solved the final compartment of the treat puzzle.",
    2: "The solar camping setup used a 120-watt folding panel and a waterproof lunch box for the controller. The solar lantern comparison tested six compact lanterns for charge time and nighttime brightness. The kitchen tarp used an angled ridgeline to divert runoff away from the stove and food boxes.",
    3: "The humming bridge produces a note near 440 hertz through evenly spaced railings resonating in wind. The suspension bridge whistles through a narrow seam beneath the eastern walkway during winter gusts. The percussion footbridge makes different notes as raindrops strike its deck panels.",
    4: "The night-shift cabinet is blue and is restocked Thursday at 6 a.m. The night-bus shelf has travel books and warm drinks beside the depot. The hospital reading cart visits three floors during the overnight shift.",
    5: "At the grandmother marathon her family met her at kilometer 38 with orange flags. The marathon post has 2852 points. The team waited 34 years for a championship and scored with 18 seconds left. The championship post has 5447 points. Saved the championship story.",
    6: "The sourdough skyline took three attempts and nearly fourteen hours to shape. The museum guard filled nineteen pocket notebooks in five years. The cartoon drawing trick moves eyebrows two millimeters.",
    7: "The transparent keyboard uses silent tactile switches and a hand-polished acrylic case. The keyboard post has 2679 points. The arcade runs twelve restored titles with 1980s-style controls. The arcade post has 3890 points. Saved the arcade story.",
    8: "The street musician concert was on platform seven. The percussion footbridge produces distinct notes when raindrops strike different deck panels. City bridge microphones beneath the deck map bass notes to slow blue pulses.",
    9: "The fox Copper has 4236 points. Residents keep a respectful distance. The kayaking dog Pepper has 3717 points and waited for a second lap around the lake. The rescue cat Miso has 2506 points. The top-two point gap is 519 points.",
}
# Independent valid equivalents, used both through the official grader and unit checks.
EQUIVALENTS = {
    0: ANSWERS[0]
    .replace("4.2 meters", "420 cm")
    .replace("reclaimed oak", "salvaged oak"),
    1: ANSWERS[1].replace("eleven days", "11 days"),
    2: ANSWERS[2]
    .replace("120-watt", "0.12 kW")
    .replace("six compact lanterns", "6 lanterns"),
    3: ANSWERS[3].replace("440 hertz", "0.44 kHz").replace("beneath", "under"),
    4: ANSWERS[4]
    .replace("Thursday at 6 a.m.", "Thursdays at 06:00.")
    .replace("warm drinks", "hot beverages"),
    5: ANSWERS[5]
    .replace("kilometer 38", "38 km")
    .replace("34 years", "thirty-four years")
    .replace("18 seconds left", "eighteen seconds remaining"),
    6: ANSWERS[6]
    .replace("fourteen hours", "840 minutes")
    .replace("two millimeters", "0.2 cm"),
    7: ANSWERS[7]
    .replace("silent tactile", "quiet tactile")
    .replace("acrylic", "Perspex")
    .replace("twelve restored titles", "12 games")
    .replace("1980s-style", "eighties-style"),
    8: ANSWERS[8]
    .replace("platform seven", "platform 7")
    .replace("microphones beneath", "mics under"),
    9: ANSWERS[9]
    .replace("4236", "4,236")
    .replace("3717", "3,717")
    .replace("2506", "2,506")
    .replace("keep a respectful distance", "give the animal space"),
}
# A wrong secondary fact must fail even when the entire former single-post answer is present.
WRONG = {
    0: ("pine and brass", "pine and steel"),
    1: ("spring open house", "autumn open house"),
    2: ("six compact lanterns", "seven compact lanterns"),
    3: ("eastern walkway", "western walkway"),
    4: ("three floors", "four floors"),
    5: ("18 seconds", "28 seconds"),
    6: ("nineteen pocket notebooks", "ninety pocket notebooks"),
    7: ("twelve restored titles", "thirteen restored titles"),
    8: ("slow blue pulses", "fast red pulses"),
    9: ("519 points", "520 points"),
}
CONTRADICTIONS = {
    0: " The bookshop desk is steel.",
    1: " Basil met the volunteer at an autumn open house.",
    2: " The lantern test measured only cost, not brightness.",
    3: " The suspension bridge sound comes from cables.",
    4: " The hospital cart visits four floors.",
    5: " The deciding goal came with 28 seconds left.",
    6: " The museum guard filled 29 notebooks.",
    7: " The arcade has 13 games.",
    8: " The city bridge produces fast red pulses.",
    9: " The rescue cat Miso has the most points.",
}
