-- Audited synthetic HF seed; full real schema and rows. Not E2E evidence.
BEGIN TRANSACTION;
CREATE TABLE album_tags (
	album_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	PRIMARY KEY (album_id, tag_id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id)
);
INSERT INTO "album_tags" VALUES(1,1);
INSERT INTO "album_tags" VALUES(1,2);
INSERT INTO "album_tags" VALUES(1,3);
INSERT INTO "album_tags" VALUES(1,4);
INSERT INTO "album_tags" VALUES(2,5);
INSERT INTO "album_tags" VALUES(2,6);
INSERT INTO "album_tags" VALUES(2,7);
INSERT INTO "album_tags" VALUES(2,4);
INSERT INTO "album_tags" VALUES(3,8);
INSERT INTO "album_tags" VALUES(3,9);
INSERT INTO "album_tags" VALUES(3,10);
INSERT INTO "album_tags" VALUES(3,11);
INSERT INTO "album_tags" VALUES(4,12);
INSERT INTO "album_tags" VALUES(4,13);
INSERT INTO "album_tags" VALUES(4,14);
INSERT INTO "album_tags" VALUES(4,11);
INSERT INTO "album_tags" VALUES(5,15);
INSERT INTO "album_tags" VALUES(5,16);
INSERT INTO "album_tags" VALUES(5,17);
INSERT INTO "album_tags" VALUES(5,18);
INSERT INTO "album_tags" VALUES(6,19);
INSERT INTO "album_tags" VALUES(6,20);
INSERT INTO "album_tags" VALUES(6,21);
INSERT INTO "album_tags" VALUES(6,18);
INSERT INTO "album_tags" VALUES(7,22);
INSERT INTO "album_tags" VALUES(7,23);
INSERT INTO "album_tags" VALUES(7,24);
INSERT INTO "album_tags" VALUES(7,25);
INSERT INTO "album_tags" VALUES(8,26);
INSERT INTO "album_tags" VALUES(8,27);
INSERT INTO "album_tags" VALUES(8,28);
INSERT INTO "album_tags" VALUES(8,25);
INSERT INTO "album_tags" VALUES(9,29);
INSERT INTO "album_tags" VALUES(9,30);
INSERT INTO "album_tags" VALUES(9,31);
INSERT INTO "album_tags" VALUES(9,32);
INSERT INTO "album_tags" VALUES(10,33);
INSERT INTO "album_tags" VALUES(10,34);
INSERT INTO "album_tags" VALUES(10,35);
INSERT INTO "album_tags" VALUES(10,32);
INSERT INTO "album_tags" VALUES(11,36);
INSERT INTO "album_tags" VALUES(11,37);
INSERT INTO "album_tags" VALUES(11,38);
INSERT INTO "album_tags" VALUES(11,39);
INSERT INTO "album_tags" VALUES(12,40);
INSERT INTO "album_tags" VALUES(12,41);
INSERT INTO "album_tags" VALUES(12,42);
INSERT INTO "album_tags" VALUES(12,39);
INSERT INTO "album_tags" VALUES(13,43);
INSERT INTO "album_tags" VALUES(13,44);
INSERT INTO "album_tags" VALUES(13,45);
INSERT INTO "album_tags" VALUES(13,46);
INSERT INTO "album_tags" VALUES(14,47);
INSERT INTO "album_tags" VALUES(14,48);
INSERT INTO "album_tags" VALUES(14,49);
INSERT INTO "album_tags" VALUES(14,46);
INSERT INTO "album_tags" VALUES(15,50);
INSERT INTO "album_tags" VALUES(15,51);
INSERT INTO "album_tags" VALUES(15,52);
INSERT INTO "album_tags" VALUES(15,53);
INSERT INTO "album_tags" VALUES(16,54);
INSERT INTO "album_tags" VALUES(16,55);
INSERT INTO "album_tags" VALUES(16,56);
INSERT INTO "album_tags" VALUES(16,53);
INSERT INTO "album_tags" VALUES(17,57);
INSERT INTO "album_tags" VALUES(17,58);
INSERT INTO "album_tags" VALUES(17,59);
INSERT INTO "album_tags" VALUES(17,60);
INSERT INTO "album_tags" VALUES(18,61);
INSERT INTO "album_tags" VALUES(18,62);
INSERT INTO "album_tags" VALUES(18,63);
INSERT INTO "album_tags" VALUES(18,60);
INSERT INTO "album_tags" VALUES(19,64);
INSERT INTO "album_tags" VALUES(19,65);
INSERT INTO "album_tags" VALUES(19,66);
INSERT INTO "album_tags" VALUES(19,11);
INSERT INTO "album_tags" VALUES(20,67);
INSERT INTO "album_tags" VALUES(20,68);
INSERT INTO "album_tags" VALUES(20,69);
INSERT INTO "album_tags" VALUES(20,11);
INSERT INTO "album_tags" VALUES(21,70);
INSERT INTO "album_tags" VALUES(21,71);
INSERT INTO "album_tags" VALUES(21,72);
INSERT INTO "album_tags" VALUES(21,4);
INSERT INTO "album_tags" VALUES(22,73);
INSERT INTO "album_tags" VALUES(22,74);
INSERT INTO "album_tags" VALUES(22,75);
INSERT INTO "album_tags" VALUES(22,4);
INSERT INTO "album_tags" VALUES(23,76);
INSERT INTO "album_tags" VALUES(23,77);
INSERT INTO "album_tags" VALUES(23,78);
INSERT INTO "album_tags" VALUES(23,39);
INSERT INTO "album_tags" VALUES(24,79);
INSERT INTO "album_tags" VALUES(24,80);
INSERT INTO "album_tags" VALUES(24,81);
INSERT INTO "album_tags" VALUES(24,39);
INSERT INTO "album_tags" VALUES(25,1);
INSERT INTO "album_tags" VALUES(25,2);
INSERT INTO "album_tags" VALUES(25,3);
INSERT INTO "album_tags" VALUES(25,39);
INSERT INTO "album_tags" VALUES(26,3);
INSERT INTO "album_tags" VALUES(26,82);
INSERT INTO "album_tags" VALUES(26,5);
INSERT INTO "album_tags" VALUES(26,39);
INSERT INTO "album_tags" VALUES(27,70);
INSERT INTO "album_tags" VALUES(27,72);
INSERT INTO "album_tags" VALUES(27,28);
INSERT INTO "album_tags" VALUES(27,4);
INSERT INTO "album_tags" VALUES(28,28);
INSERT INTO "album_tags" VALUES(28,71);
INSERT INTO "album_tags" VALUES(28,73);
INSERT INTO "album_tags" VALUES(28,4);
INSERT INTO "album_tags" VALUES(29,83);
INSERT INTO "album_tags" VALUES(29,8);
INSERT INTO "album_tags" VALUES(29,12);
INSERT INTO "album_tags" VALUES(29,25);
INSERT INTO "album_tags" VALUES(30,12);
INSERT INTO "album_tags" VALUES(30,13);
INSERT INTO "album_tags" VALUES(30,14);
INSERT INTO "album_tags" VALUES(30,25);
INSERT INTO "album_tags" VALUES(31,76);
INSERT INTO "album_tags" VALUES(31,77);
INSERT INTO "album_tags" VALUES(31,79);
INSERT INTO "album_tags" VALUES(31,11);
INSERT INTO "album_tags" VALUES(32,79);
INSERT INTO "album_tags" VALUES(32,78);
INSERT INTO "album_tags" VALUES(32,84);
INSERT INTO "album_tags" VALUES(32,11);
INSERT INTO "album_tags" VALUES(33,26);
INSERT INTO "album_tags" VALUES(33,24);
INSERT INTO "album_tags" VALUES(33,27);
INSERT INTO "album_tags" VALUES(33,46);
INSERT INTO "album_tags" VALUES(34,27);
INSERT INTO "album_tags" VALUES(34,22);
INSERT INTO "album_tags" VALUES(34,85);
INSERT INTO "album_tags" VALUES(34,46);
INSERT INTO "album_tags" VALUES(35,36);
INSERT INTO "album_tags" VALUES(35,86);
INSERT INTO "album_tags" VALUES(35,37);
INSERT INTO "album_tags" VALUES(35,53);
INSERT INTO "album_tags" VALUES(36,37);
INSERT INTO "album_tags" VALUES(36,42);
INSERT INTO "album_tags" VALUES(36,40);
INSERT INTO "album_tags" VALUES(36,53);
INSERT INTO "album_tags" VALUES(37,57);
INSERT INTO "album_tags" VALUES(37,61);
INSERT INTO "album_tags" VALUES(37,58);
INSERT INTO "album_tags" VALUES(37,32);
INSERT INTO "album_tags" VALUES(38,58);
INSERT INTO "album_tags" VALUES(38,63);
INSERT INTO "album_tags" VALUES(38,59);
INSERT INTO "album_tags" VALUES(38,32);
INSERT INTO "album_tags" VALUES(39,29);
INSERT INTO "album_tags" VALUES(39,33);
INSERT INTO "album_tags" VALUES(39,34);
INSERT INTO "album_tags" VALUES(39,18);
INSERT INTO "album_tags" VALUES(40,34);
INSERT INTO "album_tags" VALUES(40,35);
INSERT INTO "album_tags" VALUES(40,30);
INSERT INTO "album_tags" VALUES(40,18);
INSERT INTO "album_tags" VALUES(41,87);
INSERT INTO "album_tags" VALUES(41,47);
INSERT INTO "album_tags" VALUES(41,44);
INSERT INTO "album_tags" VALUES(41,60);
INSERT INTO "album_tags" VALUES(42,44);
INSERT INTO "album_tags" VALUES(42,43);
INSERT INTO "album_tags" VALUES(42,48);
INSERT INTO "album_tags" VALUES(42,60);
INSERT INTO "album_tags" VALUES(43,88);
INSERT INTO "album_tags" VALUES(43,50);
INSERT INTO "album_tags" VALUES(43,54);
INSERT INTO "album_tags" VALUES(43,39);
INSERT INTO "album_tags" VALUES(44,54);
INSERT INTO "album_tags" VALUES(44,52);
INSERT INTO "album_tags" VALUES(44,55);
INSERT INTO "album_tags" VALUES(44,39);
INSERT INTO "album_tags" VALUES(45,64);
INSERT INTO "album_tags" VALUES(45,67);
INSERT INTO "album_tags" VALUES(45,68);
INSERT INTO "album_tags" VALUES(45,4);
INSERT INTO "album_tags" VALUES(46,68);
INSERT INTO "album_tags" VALUES(46,89);
INSERT INTO "album_tags" VALUES(46,69);
INSERT INTO "album_tags" VALUES(46,4);
INSERT INTO "album_tags" VALUES(47,15);
INSERT INTO "album_tags" VALUES(47,19);
INSERT INTO "album_tags" VALUES(47,16);
INSERT INTO "album_tags" VALUES(47,25);
INSERT INTO "album_tags" VALUES(48,16);
INSERT INTO "album_tags" VALUES(48,20);
INSERT INTO "album_tags" VALUES(48,90);
INSERT INTO "album_tags" VALUES(48,25);
INSERT INTO "album_tags" VALUES(49,1);
INSERT INTO "album_tags" VALUES(49,2);
INSERT INTO "album_tags" VALUES(49,3);
INSERT INTO "album_tags" VALUES(49,11);
INSERT INTO "album_tags" VALUES(50,3);
INSERT INTO "album_tags" VALUES(50,82);
INSERT INTO "album_tags" VALUES(50,5);
INSERT INTO "album_tags" VALUES(50,11);
INSERT INTO "album_tags" VALUES(51,70);
INSERT INTO "album_tags" VALUES(51,72);
INSERT INTO "album_tags" VALUES(51,28);
INSERT INTO "album_tags" VALUES(51,46);
INSERT INTO "album_tags" VALUES(52,28);
INSERT INTO "album_tags" VALUES(52,71);
INSERT INTO "album_tags" VALUES(52,73);
INSERT INTO "album_tags" VALUES(52,46);
INSERT INTO "album_tags" VALUES(53,83);
INSERT INTO "album_tags" VALUES(53,8);
INSERT INTO "album_tags" VALUES(53,12);
INSERT INTO "album_tags" VALUES(53,53);
INSERT INTO "album_tags" VALUES(54,12);
INSERT INTO "album_tags" VALUES(54,13);
INSERT INTO "album_tags" VALUES(54,14);
INSERT INTO "album_tags" VALUES(54,53);
INSERT INTO "album_tags" VALUES(55,76);
INSERT INTO "album_tags" VALUES(55,77);
INSERT INTO "album_tags" VALUES(55,79);
INSERT INTO "album_tags" VALUES(55,32);
INSERT INTO "album_tags" VALUES(56,79);
INSERT INTO "album_tags" VALUES(56,78);
INSERT INTO "album_tags" VALUES(56,84);
INSERT INTO "album_tags" VALUES(56,32);
INSERT INTO "album_tags" VALUES(57,26);
INSERT INTO "album_tags" VALUES(57,24);
INSERT INTO "album_tags" VALUES(57,27);
INSERT INTO "album_tags" VALUES(57,18);
INSERT INTO "album_tags" VALUES(58,27);
INSERT INTO "album_tags" VALUES(58,22);
INSERT INTO "album_tags" VALUES(58,85);
INSERT INTO "album_tags" VALUES(58,18);
INSERT INTO "album_tags" VALUES(59,36);
INSERT INTO "album_tags" VALUES(59,86);
INSERT INTO "album_tags" VALUES(59,37);
INSERT INTO "album_tags" VALUES(59,60);
INSERT INTO "album_tags" VALUES(60,37);
INSERT INTO "album_tags" VALUES(60,42);
INSERT INTO "album_tags" VALUES(60,40);
INSERT INTO "album_tags" VALUES(60,60);
INSERT INTO "album_tags" VALUES(61,57);
INSERT INTO "album_tags" VALUES(61,61);
INSERT INTO "album_tags" VALUES(61,58);
INSERT INTO "album_tags" VALUES(61,39);
INSERT INTO "album_tags" VALUES(62,58);
INSERT INTO "album_tags" VALUES(62,63);
INSERT INTO "album_tags" VALUES(62,59);
INSERT INTO "album_tags" VALUES(62,39);
INSERT INTO "album_tags" VALUES(63,29);
INSERT INTO "album_tags" VALUES(63,33);
INSERT INTO "album_tags" VALUES(63,34);
INSERT INTO "album_tags" VALUES(63,4);
INSERT INTO "album_tags" VALUES(64,34);
INSERT INTO "album_tags" VALUES(64,35);
INSERT INTO "album_tags" VALUES(64,30);
INSERT INTO "album_tags" VALUES(64,4);
INSERT INTO "album_tags" VALUES(65,87);
INSERT INTO "album_tags" VALUES(65,47);
INSERT INTO "album_tags" VALUES(65,44);
INSERT INTO "album_tags" VALUES(65,25);
INSERT INTO "album_tags" VALUES(66,44);
INSERT INTO "album_tags" VALUES(66,43);
INSERT INTO "album_tags" VALUES(66,48);
INSERT INTO "album_tags" VALUES(66,25);
INSERT INTO "album_tags" VALUES(67,88);
INSERT INTO "album_tags" VALUES(67,50);
INSERT INTO "album_tags" VALUES(67,54);
INSERT INTO "album_tags" VALUES(67,11);
INSERT INTO "album_tags" VALUES(68,54);
INSERT INTO "album_tags" VALUES(68,52);
INSERT INTO "album_tags" VALUES(68,55);
INSERT INTO "album_tags" VALUES(68,11);
INSERT INTO "album_tags" VALUES(69,64);
INSERT INTO "album_tags" VALUES(69,67);
INSERT INTO "album_tags" VALUES(69,68);
INSERT INTO "album_tags" VALUES(69,46);
INSERT INTO "album_tags" VALUES(70,68);
INSERT INTO "album_tags" VALUES(70,89);
INSERT INTO "album_tags" VALUES(70,69);
INSERT INTO "album_tags" VALUES(70,46);
INSERT INTO "album_tags" VALUES(71,15);
INSERT INTO "album_tags" VALUES(71,19);
INSERT INTO "album_tags" VALUES(71,16);
INSERT INTO "album_tags" VALUES(71,53);
INSERT INTO "album_tags" VALUES(72,16);
INSERT INTO "album_tags" VALUES(72,20);
INSERT INTO "album_tags" VALUES(72,90);
INSERT INTO "album_tags" VALUES(72,53);
INSERT INTO "album_tags" VALUES(73,1);
INSERT INTO "album_tags" VALUES(73,2);
INSERT INTO "album_tags" VALUES(73,3);
INSERT INTO "album_tags" VALUES(73,32);
INSERT INTO "album_tags" VALUES(74,3);
INSERT INTO "album_tags" VALUES(74,82);
INSERT INTO "album_tags" VALUES(74,5);
INSERT INTO "album_tags" VALUES(74,32);
INSERT INTO "album_tags" VALUES(75,70);
INSERT INTO "album_tags" VALUES(75,72);
INSERT INTO "album_tags" VALUES(75,28);
INSERT INTO "album_tags" VALUES(75,18);
INSERT INTO "album_tags" VALUES(76,28);
INSERT INTO "album_tags" VALUES(76,71);
INSERT INTO "album_tags" VALUES(76,73);
INSERT INTO "album_tags" VALUES(76,18);
INSERT INTO "album_tags" VALUES(77,83);
INSERT INTO "album_tags" VALUES(77,8);
INSERT INTO "album_tags" VALUES(77,12);
INSERT INTO "album_tags" VALUES(77,60);
INSERT INTO "album_tags" VALUES(78,12);
INSERT INTO "album_tags" VALUES(78,13);
INSERT INTO "album_tags" VALUES(78,14);
INSERT INTO "album_tags" VALUES(78,60);
INSERT INTO "album_tags" VALUES(79,76);
INSERT INTO "album_tags" VALUES(79,77);
INSERT INTO "album_tags" VALUES(79,79);
INSERT INTO "album_tags" VALUES(79,39);
INSERT INTO "album_tags" VALUES(80,79);
INSERT INTO "album_tags" VALUES(80,78);
INSERT INTO "album_tags" VALUES(80,84);
INSERT INTO "album_tags" VALUES(80,39);
CREATE TABLE albums (
	id INTEGER NOT NULL, 
	artist_id INTEGER NOT NULL, 
	label_id INTEGER NOT NULL, 
	primary_genre_id INTEGER NOT NULL, 
	scene_id INTEGER NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	slug VARCHAR(180) NOT NULL, 
	description TEXT, 
	story TEXT, 
	cover_image VARCHAR(255), 
	header_image VARCHAR(255), 
	price FLOAT, 
	release_date DATE NOT NULL, 
	track_count INTEGER, 
	duration_seconds INTEGER, 
	fan_count INTEGER, 
	catalog_no VARCHAR(40), 
	is_featured BOOLEAN, 
	is_new BOOLEAN, 
	is_editorial BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(artist_id) REFERENCES artists (id), 
	FOREIGN KEY(label_id) REFERENCES labels (id), 
	FOREIGN KEY(primary_genre_id) REFERENCES genres (id), 
	FOREIGN KEY(scene_id) REFERENCES scenes (id)
);
INSERT INTO "albums" VALUES(1,1,1,1,2,'Tidal Memory','tidal-memory','Tidal Memory by Neon Harbor folds electronic textures from Berlin into a detailed release built around dub techno, afterhours, submerged, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Tidal Memory leans on dub techno energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/tidal-memory.svg','images/banners/tidal-memory.svg',8.5,'2025-10-14',5,1210,141,'AT-042',1,1,1);
INSERT INTO "albums" VALUES(2,1,1,1,2,'Night Ferry','night-ferry','Night Ferry by Neon Harbor folds electronic textures from Berlin into a detailed release built around deep groove, modular, late deck, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Night Ferry leans on deep groove energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/night-ferry.svg','images/banners/night-ferry.svg',7.0,'2024-06-07',5,1315,177,'AT-031',0,0,0);
INSERT INTO "albums" VALUES(3,2,2,3,4,'Static Bloom','static-bloom','Static Bloom by Glass Choir folds alternative textures from London into a detailed release built around dream pop, reverb, overcast hooks, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Static Bloom leans on dream pop energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/static-bloom.svg','images/banners/static-bloom.svg',9.0,'2026-02-20',5,1275,158,'MS-118',1,1,0);
INSERT INTO "albums" VALUES(4,2,2,3,4,'Paper Signal','paper-signal','Paper Signal by Glass Choir folds alternative textures from London into a detailed release built around shoegaze, jangle, bedroom, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Paper Signal leans on shoegaze energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/paper-signal.svg','images/banners/paper-signal.svg',8.0,'2024-11-08',5,1210,195,'MS-094',0,0,0);
INSERT INTO "albums" VALUES(5,3,3,12,8,'Redline Ritual','redline-ritual','Redline Ritual by Ashen Circuit folds techno textures from Detroit into a detailed release built around warehouse, analog, strobe, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Redline Ritual leans on warehouse energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/redline-ritual.svg','images/banners/redline-ritual.svg',8.0,'2023-09-15',5,1170,176,'MR-207',0,0,0);
INSERT INTO "albums" VALUES(6,3,3,12,8,'Machine Prayer','machine-prayer','Machine Prayer by Ashen Circuit folds techno textures from Detroit into a detailed release built around acid, tool track, ferrous, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Machine Prayer leans on acid energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/machine-prayer.svg','images/banners/machine-prayer.svg',9.5,'2025-05-30',5,1275,213,'MR-223',1,1,0);
INSERT INTO "albums" VALUES(7,4,4,5,3,'Between Stations','between-stations','Between Stations by Soft Locale folds ambient textures from Tokyo into a detailed release built around commuter, late train, sleep tape, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Between Stations leans on commuter energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/between-stations.svg','images/banners/between-stations.svg',8.0,'2025-08-01',5,1235,195,'IW-052',1,1,1);
INSERT INTO "albums" VALUES(8,4,4,5,3,'Sleep Maps','sleep-maps','Sleep Maps by Soft Locale folds ambient textures from Tokyo into a detailed release built around drone, meditation, field recordings, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Sleep Maps leans on drone energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/sleep-maps.svg','images/banners/sleep-maps.svg',7.5,'2024-02-23',5,1170,231,'IW-041',0,0,0);
INSERT INTO "albums" VALUES(9,5,5,8,7,'Concrete Carnival','concrete-carnival','Concrete Carnival by South Exit folds punk textures from Sao Paulo into a detailed release built around d-beat, DIY, street flyer, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Concrete Carnival leans on d-beat energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/concrete-carnival.svg','images/banners/concrete-carnival.svg',7.5,'2025-04-11',5,1300,212,'SD-014',0,1,0);
INSERT INTO "albums" VALUES(10,5,5,8,7,'Siren Economy','siren-economy','Siren Economy by South Exit folds punk textures from Sao Paulo into a detailed release built around basement, agitprop, sprint, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Siren Economy leans on basement energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/siren-economy.svg','images/banners/siren-economy.svg',7.0,'2023-12-01',5,1235,249,'SD-008',0,0,0);
INSERT INTO "albums" VALUES(11,6,6,6,1,'Signal Debt','signal-debt','Signal Debt by Cinder Plaza folds hip-hop/rap textures from Los Angeles into a detailed release built around lyric sheet, left field, city pressure, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Signal Debt leans on lyric sheet energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/signal-debt.svg','images/banners/signal-debt.svg',8.5,'2025-09-19',5,1195,231,'ST-072',1,1,0);
INSERT INTO "albums" VALUES(12,6,6,6,1,'Blueprint Fever','blueprint-fever','Blueprint Fever by Cinder Plaza folds hip-hop/rap textures from Los Angeles into a detailed release built around jazz rap, loop heavy, basement tape, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Blueprint Fever leans on jazz rap energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/blueprint-fever.svg','images/banners/blueprint-fever.svg',8.0,'2024-03-22',5,1130,267,'ST-059',0,0,0);
INSERT INTO "albums" VALUES(13,7,7,9,5,'Blue Hour Broadcast','blue-hour-broadcast','Blue Hour Broadcast by Velvet Avenue folds jazz textures from New York into a detailed release built around late set, trio, blue room, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Blue Hour Broadcast leans on late set energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/blue-hour-broadcast.svg','images/banners/blue-hour-broadcast.svg',9.5,'2025-01-31',5,1260,249,'NSA-211',1,1,0);
INSERT INTO "albums" VALUES(14,7,7,9,5,'Lobby Mirage','lobby-mirage','Lobby Mirage by Velvet Avenue folds jazz textures from New York into a detailed release built around modal, horn blend, improv, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Lobby Mirage leans on modal energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/lobby-mirage.svg','images/banners/lobby-mirage.svg',8.0,'2023-08-18',5,1195,285,'NSA-196',0,0,0);
INSERT INTO "albums" VALUES(15,8,8,10,6,'Riverlights','riverlights','Riverlights by Salt Meadow folds folk textures from Melbourne into a detailed release built around story song, field note, river road, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Riverlights leans on story song energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/riverlights.svg','images/banners/riverlights.svg',8.0,'2025-07-11',5,1155,266,'LU-063',1,1,0);
INSERT INTO "albums" VALUES(16,8,8,10,6,'Common Thread','common-thread','Common Thread by Salt Meadow folds folk textures from Melbourne into a detailed release built around americana, soft harmonies, slow weather, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Common Thread leans on americana energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/common-thread.svg','images/banners/common-thread.svg',7.5,'2024-05-03',5,1090,303,'LU-051',0,0,0);
INSERT INTO "albums" VALUES(17,9,9,7,9,'Iron Sleep','iron-sleep','Iron Sleep by Iron Veil folds metal textures from Paris into a detailed release built around doom, ritual, cathedral reverb, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Iron Sleep leans on doom energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/iron-sleep.svg','images/banners/iron-sleep.svg',9.0,'2025-11-21',5,1220,284,'OB-119',1,1,0);
INSERT INTO "albums" VALUES(18,9,9,7,9,'Saint of Noise','saint-of-noise','Saint of Noise by Iron Veil folds metal textures from Paris into a detailed release built around blackened, ash cloud, blast beat, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Saint of Noise leans on blackened energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/saint-of-noise.svg','images/banners/saint-of-noise.svg',8.5,'2024-01-26',5,1155,321,'OB-101',0,0,0);
INSERT INTO "albums" VALUES(19,10,2,11,4,'Elastic Hearts','elastic-hearts','Elastic Hearts by Fever Arcade folds pop textures from London into a detailed release built around hook, night drive, bright chorus, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Elastic Hearts leans on hook energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/elastic-hearts.svg','images/banners/elastic-hearts.svg',9.0,'2025-12-05',5,1115,303,'MS-132',1,1,0);
INSERT INTO "albums" VALUES(20,10,2,11,4,'Mirror Mosaic','mirror-mosaic','Mirror Mosaic by Fever Arcade folds pop textures from London into a detailed release built around synth pop, gloss, dancefloor, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Mirror Mosaic leans on synth pop energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/mirror-mosaic.svg','images/banners/mirror-mosaic.svg',8.0,'2024-09-13',5,1220,339,'MS-107',0,0,0);
INSERT INTO "albums" VALUES(21,11,10,2,2,'Resin Language','resin-language','Resin Language by Mono Shrine folds experimental textures from Berlin into a detailed release built around collage, tape hiss, microtone, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Resin Language leans on collage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/resin-language.svg','images/banners/resin-language.svg',8.5,'2025-03-28',5,1180,321,'HC-014',1,1,0);
INSERT INTO "albums" VALUES(22,11,10,2,2,'Fault Choir','fault-choir','Fault Choir by Mono Shrine folds experimental textures from Berlin into a detailed release built around glitch, avant pop, noise drift, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Fault Choir leans on glitch energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/fault-choir.svg','images/banners/fault-choir.svg',8.0,'2024-07-26',5,1115,357,'HC-006',0,0,0);
INSERT INTO "albums" VALUES(23,12,6,4,1,'Harbor Burn','harbor-burn','Harbor Burn by Tide Static folds rock textures from Los Angeles into a detailed release built around psych rock, motorik, widescreen, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Harbor Burn leans on psych rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/harbor-burn.svg','images/banners/harbor-burn.svg',8.0,'2025-06-27',5,1075,338,'ST-064',1,1,0);
INSERT INTO "albums" VALUES(24,12,6,4,1,'Quiet Engine','quiet-engine','Quiet Engine by Tide Static folds rock textures from Los Angeles into a detailed release built around garage, riff driven, festival ready, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Quiet Engine leans on garage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/quiet-engine.svg','images/banners/quiet-engine.svg',7.5,'2024-04-05',5,1180,375,'ST-051',0,0,0);
INSERT INTO "albums" VALUES(25,13,1,1,1,'Static Weather','static-weather','Static Weather by Amber Relay folds electronic textures from Los Angeles into a detailed release built around dub techno, afterhours, submerged, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Static Weather leans on dub techno energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/static-weather.svg','images/banners/static-weather.svg',7.0,'2023-01-01',5,1140,356,'HC-200',1,0,0);
INSERT INTO "albums" VALUES(26,13,1,1,1,'Quiet Vector','quiet-vector','Quiet Vector by Amber Relay folds electronic textures from Los Angeles into a detailed release built around submerged, drum machine, deep groove, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Quiet Vector leans on submerged energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/quiet-vector.svg','images/banners/quiet-vector.svg',7.5,'2024-05-01',5,1245,393,'HC-240',0,0,0);
INSERT INTO "albums" VALUES(27,14,2,2,2,'Harbor Ledger','harbor-ledger','Harbor Ledger by Paper Current folds experimental textures from Berlin into a detailed release built around collage, microtone, field recordings, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Harbor Ledger leans on collage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/harbor-ledger.svg','images/banners/harbor-ledger.svg',7.5,'2024-02-04',5,1205,374,'HC-201',1,0,0);
INSERT INTO "albums" VALUES(28,14,2,2,2,'Paper Thread','paper-thread','Paper Thread by Paper Current folds experimental textures from Berlin into a detailed release built around field recordings, tape hiss, glitch, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Paper Thread leans on field recordings energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/paper-thread.svg','images/banners/paper-thread.svg',8.0,'2025-06-06',5,1310,411,'HC-241',0,1,0);
INSERT INTO "albums" VALUES(29,15,3,3,3,'River Cinema','river-cinema','River Cinema by Silver Weather folds alternative textures from Tokyo into a detailed release built around indie rock, dream pop, shoegaze, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, River Cinema leans on indie rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/river-cinema.svg','images/banners/river-cinema.svg',8.0,'2025-03-07',5,1270,392,'HC-202',1,1,0);
INSERT INTO "albums" VALUES(30,15,3,3,3,'Chrome Parade','chrome-parade','Chrome Parade by Silver Weather folds alternative textures from Tokyo into a detailed release built around shoegaze, jangle, bedroom, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Chrome Parade leans on shoegaze energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/chrome-parade.svg','images/banners/chrome-parade.svg',8.5,'2026-07-11',5,1205,429,'HC-242',0,1,0);
INSERT INTO "albums" VALUES(31,16,4,4,4,'Signal Method','signal-method','Signal Method by North Routine folds rock textures from London into a detailed release built around psych rock, motorik, garage, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Signal Method leans on psych rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/signal-method.svg','images/banners/signal-method.svg',8.5,'2026-04-10',5,1165,410,'HC-203',1,1,0);
INSERT INTO "albums" VALUES(32,16,4,4,4,'South Engine','south-engine','South Engine by North Routine folds rock textures from London into a detailed release built around garage, widescreen, burnt amp, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, South Engine leans on garage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/south-engine.svg','images/banners/south-engine.svg',9.0,'2024-08-16',5,1270,447,'HC-243',0,0,0);
INSERT INTO "albums" VALUES(33,17,5,5,5,'Blue Current','blue-current','Blue Current by Copper Bloom folds ambient textures from New York into a detailed release built around drone, sleep tape, meditation, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Blue Current leans on drone energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/blue-current.svg','images/banners/blue-current.svg',9.0,'2023-05-13',5,1230,428,'HC-204',0,0,0);
INSERT INTO "albums" VALUES(34,17,5,5,5,'Midnight Signal','midnight-signal','Midnight Signal by Copper Bloom folds ambient textures from New York into a detailed release built around meditation, commuter, soundscape, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Midnight Signal leans on meditation energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/midnight-signal.svg','images/banners/midnight-signal.svg',7.5,'2025-09-21',5,1165,465,'HC-244',0,1,0);
INSERT INTO "albums" VALUES(35,18,6,6,6,'Late Boulevard','late-boulevard','Late Boulevard by Ladder Choir folds hip-hop/rap textures from Melbourne into a detailed release built around lyric sheet, boom bap, left field, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Late Boulevard leans on lyric sheet energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/late-boulevard.svg','images/banners/late-boulevard.svg',7.0,'2024-06-16',5,1295,446,'HC-205',0,0,0);
INSERT INTO "albums" VALUES(36,18,6,6,6,'Glass Mosaic','glass-mosaic','Glass Mosaic by Ladder Choir folds hip-hop/rap textures from Melbourne into a detailed release built around left field, basement tape, jazz rap, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Glass Mosaic leans on left field energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/glass-mosaic.svg','images/banners/glass-mosaic.svg',8.0,'2026-10-02',5,1230,483,'HC-245',0,1,0);
INSERT INTO "albums" VALUES(37,19,7,7,7,'Golden Garden','golden-garden','Golden Garden by Hour Motel folds metal textures from Sao Paulo into a detailed release built around doom, blackened, ritual, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Golden Garden leans on doom energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/golden-garden.svg','images/banners/golden-garden.svg',7.5,'2025-07-19',5,1190,464,'HC-206',0,1,0);
INSERT INTO "albums" VALUES(38,19,7,7,7,'Motel Harbor','motel-harbor','Motel Harbor by Hour Motel folds metal textures from Sao Paulo into a detailed release built around ritual, blast beat, cathedral reverb, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Motel Harbor leans on ritual energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/motel-harbor.svg','images/banners/motel-harbor.svg',8.5,'2024-11-07',5,1125,501,'HC-246',0,0,0);
INSERT INTO "albums" VALUES(39,20,8,8,8,'Quiet Transit','quiet-transit','Quiet Transit by Signal Lake folds punk textures from Detroit into a detailed release built around d-beat, basement, agitprop, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Quiet Transit leans on d-beat energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/quiet-transit.svg','images/banners/quiet-transit.svg',8.0,'2026-08-22',5,1255,482,'HC-207',0,1,0);
INSERT INTO "albums" VALUES(40,20,8,8,8,'Stone Circuit','stone-circuit','Stone Circuit by Signal Lake folds punk textures from Detroit into a detailed release built around agitprop, sprint, DIY, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Stone Circuit leans on agitprop energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/stone-circuit.svg','images/banners/stone-circuit.svg',9.0,'2025-01-12',5,1190,519,'HC-247',0,1,0);
INSERT INTO "albums" VALUES(41,21,9,9,9,'Paper Archive','paper-archive','Paper Archive by Delta Hall folds jazz textures from Paris into a detailed release built around spiritual, modal, trio, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Paper Archive leans on spiritual energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/paper-archive.svg','images/banners/paper-archive.svg',8.5,'2023-09-01',5,1150,500,'HC-208',0,0,0);
INSERT INTO "albums" VALUES(42,21,9,9,9,'Delta Minutes','delta-minutes','Delta Minutes by Delta Hall folds jazz textures from Paris into a detailed release built around trio, late set, horn blend, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Delta Minutes leans on trio energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/delta-minutes.svg','images/banners/delta-minutes.svg',7.5,'2026-02-17',5,1255,537,'HC-248',0,1,0);
INSERT INTO "albums" VALUES(43,22,10,10,1,'Chrome Pattern','chrome-pattern','Chrome Pattern by Mirror Union folds folk textures from Los Angeles into a detailed release built around acoustic, story song, americana, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Chrome Pattern leans on acoustic energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/chrome-pattern.svg','images/banners/chrome-pattern.svg',9.0,'2024-10-04',5,1215,518,'HC-209',0,0,0);
INSERT INTO "albums" VALUES(44,22,10,10,1,'Velvet Weather','velvet-weather','Velvet Weather by Mirror Union folds folk textures from Los Angeles into a detailed release built around americana, river road, soft harmonies, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Velvet Weather leans on americana energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/velvet-weather.svg','images/banners/velvet-weather.svg',8.0,'2024-03-22',5,1150,555,'HC-249',0,0,0);
INSERT INTO "albums" VALUES(45,23,1,11,2,'South Dusk','south-dusk','South Dusk by Quiet Metric folds pop textures from Berlin into a detailed release built around hook, synth pop, gloss, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, South Dusk leans on hook energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/south-dusk.svg','images/banners/south-dusk.svg',7.0,'2025-11-07',5,1110,536,'HC-210',0,1,0);
INSERT INTO "albums" VALUES(46,23,1,11,2,'Open Ledger','open-ledger','Open Ledger by Quiet Metric folds pop textures from Berlin into a detailed release built around gloss, heartbreak, dancefloor, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Open Ledger leans on gloss energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/open-ledger.svg','images/banners/open-ledger.svg',8.5,'2025-04-03',5,1215,573,'HC-250',0,1,0);
INSERT INTO "albums" VALUES(47,24,2,12,3,'Midnight Vector','midnight-vector','Midnight Vector by Blue Archive folds techno textures from Tokyo into a detailed release built around warehouse, acid, analog, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Midnight Vector leans on warehouse energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/midnight-vector.svg','images/banners/midnight-vector.svg',7.5,'2026-01-10',5,1175,554,'HC-211',0,1,0);
INSERT INTO "albums" VALUES(48,24,2,12,3,'After Cinema','after-cinema','After Cinema by Blue Archive folds techno textures from Tokyo into a detailed release built around analog, tool track, four on the floor, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, After Cinema leans on analog energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/after-cinema.svg','images/banners/after-cinema.svg',9.0,'2026-05-08',5,1110,591,'HC-251',0,1,0);
INSERT INTO "albums" VALUES(49,25,3,1,4,'Glass Thread','glass-thread','Glass Thread by Stair Pattern folds electronic textures from London into a detailed release built around dub techno, afterhours, submerged, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Glass Thread leans on dub techno energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/glass-thread.svg','images/banners/glass-thread.svg',8.0,'2023-02-13',5,1070,572,'HC-212',0,0,0);
INSERT INTO "albums" VALUES(50,25,3,1,4,'Broken Method','broken-method','Broken Method by Stair Pattern folds electronic textures from London into a detailed release built around submerged, drum machine, deep groove, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Broken Method leans on submerged energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/broken-method.svg','images/banners/broken-method.svg',7.5,'2024-06-13',5,1175,609,'HC-252',0,0,0);
INSERT INTO "albums" VALUES(51,26,4,2,5,'Motel Parade','motel-parade','Motel Parade by Velvet Current folds experimental textures from New York into a detailed release built around collage, microtone, field recordings, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Motel Parade leans on collage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/motel-parade.svg','images/banners/motel-parade.svg',8.5,'2024-03-16',5,1135,590,'HC-213',0,0,0);
INSERT INTO "albums" VALUES(52,26,4,2,5,'Static Current','static-current','Static Current by Velvet Current folds experimental textures from New York into a detailed release built around field recordings, tape hiss, glitch, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Static Current leans on field recordings energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/static-current.svg','images/banners/static-current.svg',8.0,'2025-07-18',5,1240,627,'HC-253',0,1,0);
INSERT INTO "albums" VALUES(53,27,5,3,6,'Stone Engine','stone-engine','Stone Engine by Harbor Study folds alternative textures from Melbourne into a detailed release built around indie rock, dream pop, shoegaze, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Stone Engine leans on indie rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/stone-engine.svg','images/banners/stone-engine.svg',9.0,'2025-04-19',5,1200,608,'HC-214',0,1,0);
INSERT INTO "albums" VALUES(54,27,5,3,6,'Harbor Boulevard','harbor-boulevard','Harbor Boulevard by Harbor Study folds alternative textures from Melbourne into a detailed release built around shoegaze, jangle, bedroom, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Harbor Boulevard leans on shoegaze energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/harbor-boulevard.svg','images/banners/harbor-boulevard.svg',8.5,'2026-08-23',5,1305,645,'HC-254',0,1,0);
INSERT INTO "albums" VALUES(55,28,6,4,7,'Delta Signal','delta-signal','Delta Signal by Street Lantern folds rock textures from Sao Paulo into a detailed release built around psych rock, motorik, garage, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Delta Signal leans on psych rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/delta-signal.svg','images/banners/delta-signal.svg',7.0,'2026-05-22',5,1265,626,'HC-215',0,1,0);
INSERT INTO "albums" VALUES(56,28,6,4,7,'River Garden','river-garden','River Garden by Street Lantern folds rock textures from Sao Paulo into a detailed release built around garage, widescreen, burnt amp, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, River Garden leans on garage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/river-garden.svg','images/banners/river-garden.svg',9.0,'2024-09-04',5,1200,663,'HC-255',0,0,0);
INSERT INTO "albums" VALUES(57,29,7,5,8,'Velvet Mosaic','velvet-mosaic','Velvet Mosaic by Noon Frame folds ambient textures from Detroit into a detailed release built around drone, sleep tape, meditation, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Velvet Mosaic leans on drone energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/velvet-mosaic.svg','images/banners/velvet-mosaic.svg',7.5,'2023-06-01',5,1330,644,'HC-216',0,0,0);
INSERT INTO "albums" VALUES(58,29,7,5,8,'Signal Transit','signal-transit','Signal Transit by Noon Frame folds ambient textures from Detroit into a detailed release built around meditation, commuter, soundscape, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Signal Transit leans on meditation energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/signal-transit.svg','images/banners/signal-transit.svg',7.5,'2025-10-09',5,1265,681,'HC-256',0,1,0);
INSERT INTO "albums" VALUES(59,30,8,6,9,'Open Harbor','open-harbor','Open Harbor by Low Atlas folds hip-hop/rap textures from Paris into a detailed release built around lyric sheet, boom bap, left field, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Open Harbor leans on lyric sheet energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/open-harbor.svg','images/banners/open-harbor.svg',8.0,'2024-07-04',5,1225,662,'HC-217',0,0,0);
INSERT INTO "albums" VALUES(60,30,8,6,9,'Blue Archive','blue-archive','Blue Archive by Low Atlas folds hip-hop/rap textures from Paris into a detailed release built around left field, basement tape, jazz rap, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Blue Archive leans on left field energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/blue-archive.svg','images/banners/blue-archive.svg',8.0,'2026-11-14',5,1160,699,'HC-257',0,1,0);
INSERT INTO "albums" VALUES(61,31,9,7,1,'After Circuit','after-circuit','After Circuit by Chrome Willow folds metal textures from Los Angeles into a detailed release built around doom, blackened, ritual, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, After Circuit leans on doom energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/after-circuit.svg','images/banners/after-circuit.svg',8.5,'2025-08-07',5,1290,680,'HC-218',0,1,0);
INSERT INTO "albums" VALUES(62,31,9,7,1,'Late Pattern','late-pattern','Late Pattern by Chrome Willow folds metal textures from Los Angeles into a detailed release built around ritual, blast beat, cathedral reverb, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Late Pattern leans on ritual energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/late-pattern.svg','images/banners/late-pattern.svg',8.5,'2024-01-19',5,1225,717,'HC-258',0,0,0);
INSERT INTO "albums" VALUES(63,32,10,8,2,'Broken Minutes','broken-minutes','Broken Minutes by Radio Meadow folds punk textures from Berlin into a detailed release built around d-beat, basement, agitprop, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Broken Minutes leans on d-beat energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/broken-minutes.svg','images/banners/broken-minutes.svg',9.0,'2026-09-10',5,1185,698,'HC-219',0,1,0);
INSERT INTO "albums" VALUES(64,32,10,8,2,'Golden Dusk','golden-dusk','Golden Dusk by Radio Meadow folds punk textures from Berlin into a detailed release built around agitprop, sprint, DIY, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Golden Dusk leans on agitprop energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/golden-dusk.svg','images/banners/golden-dusk.svg',9.0,'2025-02-24',5,1120,735,'HC-259',0,1,0);
INSERT INTO "albums" VALUES(65,33,1,9,3,'Static Weather','static-weather-fault-parade','Static Weather by Fault Parade folds jazz textures from Tokyo into a detailed release built around spiritual, modal, trio, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Static Weather leans on spiritual energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/static-weather-fault-parade.svg','images/banners/static-weather-fault-parade.svg',7.0,'2023-10-13',5,1250,716,'HC-220',0,0,0);
INSERT INTO "albums" VALUES(66,33,1,9,3,'Quiet Vector','quiet-vector-fault-parade','Quiet Vector by Fault Parade folds jazz textures from Tokyo into a detailed release built around trio, late set, horn blend, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Quiet Vector leans on trio energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/quiet-vector-fault-parade.svg','images/banners/quiet-vector-fault-parade.svg',7.5,'2026-03-05',5,1185,753,'HC-260',0,1,0);
INSERT INTO "albums" VALUES(67,34,2,10,4,'Harbor Ledger','harbor-ledger-static-ledger','Harbor Ledger by Static Ledger folds folk textures from London into a detailed release built around acoustic, story song, americana, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Harbor Ledger leans on acoustic energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/harbor-ledger-static-ledger.svg','images/banners/harbor-ledger-static-ledger.svg',7.5,'2024-11-16',5,1145,734,'HC-221',0,0,0);
INSERT INTO "albums" VALUES(68,34,2,10,4,'Paper Thread','paper-thread-static-ledger','Paper Thread by Static Ledger folds folk textures from London into a detailed release built around americana, river road, soft harmonies, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Paper Thread leans on americana energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/paper-thread-static-ledger.svg','images/banners/paper-thread-static-ledger.svg',8.0,'2024-04-10',5,1250,771,'HC-261',0,0,0);
INSERT INTO "albums" VALUES(69,35,3,11,5,'River Cinema','river-cinema-stone-balcony','River Cinema by Stone Balcony folds pop textures from New York into a detailed release built around hook, synth pop, gloss, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, River Cinema leans on hook energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/river-cinema-stone-balcony.svg','images/banners/river-cinema-stone-balcony.svg',8.0,'2025-01-19',5,1210,752,'HC-222',0,1,0);
INSERT INTO "albums" VALUES(70,35,3,11,5,'Chrome Parade','chrome-parade-stone-balcony','Chrome Parade by Stone Balcony folds pop textures from New York into a detailed release built around gloss, heartbreak, dancefloor, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Chrome Parade leans on gloss energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/chrome-parade-stone-balcony.svg','images/banners/chrome-parade-stone-balcony.svg',8.5,'2025-05-15',5,1145,789,'HC-262',0,1,0);
INSERT INTO "albums" VALUES(71,36,4,12,6,'Signal Method','signal-method-west-transit','Signal Method by West Transit folds techno textures from Melbourne into a detailed release built around warehouse, acid, analog, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Signal Method leans on warehouse energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/signal-method-west-transit.svg','images/banners/signal-method-west-transit.svg',8.5,'2026-02-22',5,1105,770,'HC-223',0,1,0);
INSERT INTO "albums" VALUES(72,36,4,12,6,'South Engine','south-engine-west-transit','South Engine by West Transit folds techno textures from Melbourne into a detailed release built around analog, tool track, four on the floor, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, South Engine leans on analog energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/south-engine-west-transit.svg','images/banners/south-engine-west-transit.svg',9.0,'2026-06-20',5,1210,807,'HC-263',0,1,0);
INSERT INTO "albums" VALUES(73,37,5,1,7,'Blue Current','blue-current-echo-dividend','Blue Current by Echo Dividend folds electronic textures from Sao Paulo into a detailed release built around dub techno, afterhours, submerged, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Blue Current leans on dub techno energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/blue-current-echo-dividend.svg','images/banners/blue-current-echo-dividend.svg',9.0,'2023-03-01',5,1170,788,'HC-224',0,0,0);
INSERT INTO "albums" VALUES(74,37,5,1,7,'Midnight Signal','midnight-signal-echo-dividend','Midnight Signal by Echo Dividend folds electronic textures from Sao Paulo into a detailed release built around submerged, drum machine, deep groove, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Midnight Signal leans on submerged energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/midnight-signal-echo-dividend.svg','images/banners/midnight-signal-echo-dividend.svg',7.5,'2024-07-01',5,1105,825,'HC-264',0,0,0);
INSERT INTO "albums" VALUES(75,38,6,2,8,'Late Boulevard','late-boulevard-cloud-bureau','Late Boulevard by Cloud Bureau folds experimental textures from Detroit into a detailed release built around collage, microtone, field recordings, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Late Boulevard leans on collage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/late-boulevard-cloud-bureau.svg','images/banners/late-boulevard-cloud-bureau.svg',7.0,'2024-04-04',5,1065,806,'HC-225',0,0,0);
INSERT INTO "albums" VALUES(76,38,6,2,8,'Glass Mosaic','glass-mosaic-cloud-bureau','Glass Mosaic by Cloud Bureau folds experimental textures from Detroit into a detailed release built around field recordings, tape hiss, glitch, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Glass Mosaic leans on field recordings energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/glass-mosaic-cloud-bureau.svg','images/banners/glass-mosaic-cloud-bureau.svg',8.0,'2025-08-06',5,1170,843,'HC-265',0,1,0);
INSERT INTO "albums" VALUES(77,39,7,3,9,'Golden Garden','golden-garden-ridge-cinema','Golden Garden by Ridge Cinema folds alternative textures from Paris into a detailed release built around indie rock, dream pop, shoegaze, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Golden Garden leans on indie rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/golden-garden-ridge-cinema.svg','images/banners/golden-garden-ridge-cinema.svg',7.5,'2025-05-07',5,1130,824,'HC-226',0,1,0);
INSERT INTO "albums" VALUES(78,39,7,3,9,'Motel Harbor','motel-harbor-ridge-cinema','Motel Harbor by Ridge Cinema folds alternative textures from Paris into a detailed release built around shoegaze, jangle, bedroom, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Motel Harbor leans on shoegaze energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/motel-harbor-ridge-cinema.svg','images/banners/motel-harbor-ridge-cinema.svg',8.5,'2026-09-11',5,1235,861,'HC-266',0,1,0);
INSERT INTO "albums" VALUES(79,40,8,4,1,'Quiet Transit','quiet-transit-hollow-method','Quiet Transit by Hollow Method folds rock textures from Los Angeles into a detailed release built around psych rock, motorik, garage, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Quiet Transit leans on psych rock energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/quiet-transit-hollow-method.svg','images/banners/quiet-transit-hollow-method.svg',8.0,'2026-06-10',5,1195,842,'HC-227',0,1,0);
INSERT INTO "albums" VALUES(80,40,8,4,1,'Stone Circuit','stone-circuit-hollow-method','Stone Circuit by Hollow Method folds rock textures from Los Angeles into a detailed release built around garage, widescreen, burnt amp, tactile arrangements, and patient pacing.','Recorded for the WebHarbor Bandcamp mirror as a fully local release package, Stone Circuit leans on garage energy while keeping the visual and written presentation tight enough for benchmark tasks.','images/covers/stone-circuit-hollow-method.svg','images/banners/stone-circuit-hollow-method.svg',9.0,'2024-10-16',5,1300,879,'HC-267',0,0,0);
CREATE TABLE artists (
	id INTEGER NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	slug VARCHAR(160) NOT NULL, 
	location VARCHAR(120), 
	bio TEXT, 
	headline VARCHAR(180), 
	formed_year INTEGER, 
	follow_count INTEGER, 
	avatar_image VARCHAR(255), 
	hero_image VARCHAR(255), 
	scene_id INTEGER NOT NULL, 
	label_id INTEGER NOT NULL, 
	primary_genre_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(scene_id) REFERENCES scenes (id), 
	FOREIGN KEY(label_id) REFERENCES labels (id), 
	FOREIGN KEY(primary_genre_id) REFERENCES genres (id)
);
INSERT INTO "artists" VALUES(1,'Neon Harbor','neon-harbor','Berlin, Germany','Neon Harbor build patient club music from modular haze, train-window reflections, and low-end pressure designed for the final hour of the night.','Dub silhouettes and rail-line bass pressure.',2015,1200,'images/artists/neon-harbor-avatar.svg','images/artists/neon-harbor-hero.svg',2,1,1);
INSERT INTO "artists" VALUES(2,'Glass Choir','glass-choir','London, United Kingdom','Glass Choir turn small-room guitar songs into widescreen nighttime records, leaving enough static in the mix to keep every chorus grounded.','Guitar shimmer with stairwell echo and commuter melancholy.',2016,1343,'images/artists/glass-choir-avatar.svg','images/artists/glass-choir-hero.svg',4,2,3);
INSERT INTO "artists" VALUES(3,'Ashen Circuit','ashen-circuit','Detroit, United States','Ashen Circuit work out of a one-room studio stacked with drum machines, borrowed test equipment, and lovingly repaired mixers.','Machine discipline with rust-belt force and analog grit.',2017,1486,'images/artists/ashen-circuit-avatar.svg','images/artists/ashen-circuit-hero.svg',8,3,12);
INSERT INTO "artists" VALUES(4,'Soft Locale','soft-locale','Tokyo, Japan','Soft Locale map movement through stations, elevators, and rain channels into gently detailed records full of piano dust and field recording glow.','Commuter ambient for reflective trains and dim apartment corners.',2018,1629,'images/artists/soft-locale-avatar.svg','images/artists/soft-locale-hero.svg',3,4,5);
INSERT INTO "artists" VALUES(5,'South Exit','south-exit','Sao Paulo, Brazil','South Exit play sprint-length songs built from hand-painted flyers, blown amps, and city pressure released at full velocity.','Fast songs, street posters, and DIY urgency.',2019,1772,'images/artists/south-exit-avatar.svg','images/artists/south-exit-hero.svg',7,5,8);
INSERT INTO "artists" VALUES(6,'Cinder Plaza','cinder-plaza','Los Angeles, United States','Cinder Plaza thread jazz-adjacent loops, voice notes, and concrete percussion into detail-rich rap records with cinematic pacing.','Sharp verses, bruised synths, and freeway-night hooks.',2020,1915,'images/artists/cinder-plaza-avatar.svg','images/artists/cinder-plaza-hero.svg',1,6,6);
INSERT INTO "artists" VALUES(7,'Velvet Avenue','velvet-avenue','New York, United States','Velvet Avenue record live takes with the room left intact, building jazz records that feel like late-set discoveries with a patient sense of space.','Blue-room improvisation with downtown velvet and brass glow.',2021,2058,'images/artists/velvet-avenue-avatar.svg','images/artists/velvet-avenue-hero.svg',5,7,9);
INSERT INTO "artists" VALUES(8,'Salt Meadow','salt-meadow','Melbourne, Australia','Salt Meadow turn notebooks, back-porch harmonies, and road-case acoustics into richly specific folk records.','Field-note songwriting with dusk harmonies and weathered detail.',2022,2201,'images/artists/salt-meadow-avatar.svg','images/artists/salt-meadow-hero.svg',6,8,10);
INSERT INTO "artists" VALUES(9,'Iron Veil','iron-veil','Paris, France','Iron Veil stretch doom, black metal atmosphere, and choir samples into heavy records that feel ceremonial rather than theatrical.','Cathedral reverb, iron filings, and ritual pressure.',2023,2344,'images/artists/iron-veil-avatar.svg','images/artists/iron-veil-hero.svg',9,9,7);
INSERT INTO "artists" VALUES(10,'Fever Arcade','fever-arcade','London, United Kingdom','Fever Arcade make sharp pop records whose production leaves just enough room for hallway echo and emotional static.','Neon chorus writing with club bruises and soft-focus hooks.',2015,2487,'images/artists/fever-arcade-avatar.svg','images/artists/fever-arcade-hero.svg',4,2,11);
INSERT INTO "artists" VALUES(11,'Mono Shrine','mono-shrine','Berlin, Germany','Mono Shrine fold chant fragments, room-tone edits, and damaged synth timbres into experimental pop that still lands emotionally.','Tape haze, microtonal hooks, and collage architecture.',2016,2630,'images/artists/mono-shrine-avatar.svg','images/artists/mono-shrine-hero.svg',2,10,2);
INSERT INTO "artists" VALUES(12,'Tide Static','tide-static','Los Angeles, United States','Tide Static write road-length rock songs that feel as interested in momentum and tone color as they are in choruses.','Motorik travel songs and blown-speaker optimism.',2017,2773,'images/artists/tide-static-avatar.svg','images/artists/tide-static-hero.svg',1,6,4);
INSERT INTO "artists" VALUES(13,'Amber Relay','amber-relay','Los Angeles, United States','Amber Relay operate inside the Los Angeles scene, shaping electronic records that favor texture, place, and carefully staged physical editions.','Electronic releases tuned to Los Angeles after-dark energy.',2018,2916,'images/artists/amber-relay-avatar.svg','images/artists/amber-relay-hero.svg',1,1,1);
INSERT INTO "artists" VALUES(14,'Paper Current','paper-current','Berlin, Germany','Paper Current operate inside the Berlin scene, shaping experimental records that favor texture, place, and carefully staged physical editions.','Experimental releases tuned to Berlin after-dark energy.',2019,3059,'images/artists/paper-current-avatar.svg','images/artists/paper-current-hero.svg',2,2,2);
INSERT INTO "artists" VALUES(15,'Silver Weather','silver-weather','Tokyo, Japan','Silver Weather operate inside the Tokyo scene, shaping alternative records that favor texture, place, and carefully staged physical editions.','Alternative releases tuned to Tokyo after-dark energy.',2020,3202,'images/artists/silver-weather-avatar.svg','images/artists/silver-weather-hero.svg',3,3,3);
INSERT INTO "artists" VALUES(16,'North Routine','north-routine','London, United Kingdom','North Routine operate inside the London scene, shaping rock records that favor texture, place, and carefully staged physical editions.','Rock releases tuned to London after-dark energy.',2021,3345,'images/artists/north-routine-avatar.svg','images/artists/north-routine-hero.svg',4,4,4);
INSERT INTO "artists" VALUES(17,'Copper Bloom','copper-bloom','New York, United States','Copper Bloom operate inside the New York scene, shaping ambient records that favor texture, place, and carefully staged physical editions.','Ambient releases tuned to New York after-dark energy.',2022,3488,'images/artists/copper-bloom-avatar.svg','images/artists/copper-bloom-hero.svg',5,5,5);
INSERT INTO "artists" VALUES(18,'Ladder Choir','ladder-choir','Melbourne, Australia','Ladder Choir operate inside the Melbourne scene, shaping hip-hop/rap records that favor texture, place, and carefully staged physical editions.','Hip-Hop/Rap releases tuned to Melbourne after-dark energy.',2023,3631,'images/artists/ladder-choir-avatar.svg','images/artists/ladder-choir-hero.svg',6,6,6);
INSERT INTO "artists" VALUES(19,'Hour Motel','hour-motel','Sao Paulo, Brazil','Hour Motel operate inside the Sao Paulo scene, shaping metal records that favor texture, place, and carefully staged physical editions.','Metal releases tuned to Sao Paulo after-dark energy.',2015,3774,'images/artists/hour-motel-avatar.svg','images/artists/hour-motel-hero.svg',7,7,7);
INSERT INTO "artists" VALUES(20,'Signal Lake','signal-lake','Detroit, United States','Signal Lake operate inside the Detroit scene, shaping punk records that favor texture, place, and carefully staged physical editions.','Punk releases tuned to Detroit after-dark energy.',2016,3917,'images/artists/signal-lake-avatar.svg','images/artists/signal-lake-hero.svg',8,8,8);
INSERT INTO "artists" VALUES(21,'Delta Hall','delta-hall','Paris, France','Delta Hall operate inside the Paris scene, shaping jazz records that favor texture, place, and carefully staged physical editions.','Jazz releases tuned to Paris after-dark energy.',2017,4060,'images/artists/delta-hall-avatar.svg','images/artists/delta-hall-hero.svg',9,9,9);
INSERT INTO "artists" VALUES(22,'Mirror Union','mirror-union','Los Angeles, United States','Mirror Union operate inside the Los Angeles scene, shaping folk records that favor texture, place, and carefully staged physical editions.','Folk releases tuned to Los Angeles after-dark energy.',2018,4203,'images/artists/mirror-union-avatar.svg','images/artists/mirror-union-hero.svg',1,10,10);
INSERT INTO "artists" VALUES(23,'Quiet Metric','quiet-metric','Berlin, Germany','Quiet Metric operate inside the Berlin scene, shaping pop records that favor texture, place, and carefully staged physical editions.','Pop releases tuned to Berlin after-dark energy.',2019,4346,'images/artists/quiet-metric-avatar.svg','images/artists/quiet-metric-hero.svg',2,1,11);
INSERT INTO "artists" VALUES(24,'Blue Archive','blue-archive','Tokyo, Japan','Blue Archive operate inside the Tokyo scene, shaping techno records that favor texture, place, and carefully staged physical editions.','Techno releases tuned to Tokyo after-dark energy.',2020,4489,'images/artists/blue-archive-avatar.svg','images/artists/blue-archive-hero.svg',3,2,12);
INSERT INTO "artists" VALUES(25,'Stair Pattern','stair-pattern','London, United Kingdom','Stair Pattern operate inside the London scene, shaping electronic records that favor texture, place, and carefully staged physical editions.','Electronic releases tuned to London after-dark energy.',2021,4632,'images/artists/stair-pattern-avatar.svg','images/artists/stair-pattern-hero.svg',4,3,1);
INSERT INTO "artists" VALUES(26,'Velvet Current','velvet-current','New York, United States','Velvet Current operate inside the New York scene, shaping experimental records that favor texture, place, and carefully staged physical editions.','Experimental releases tuned to New York after-dark energy.',2022,4775,'images/artists/velvet-current-avatar.svg','images/artists/velvet-current-hero.svg',5,4,2);
INSERT INTO "artists" VALUES(27,'Harbor Study','harbor-study','Melbourne, Australia','Harbor Study operate inside the Melbourne scene, shaping alternative records that favor texture, place, and carefully staged physical editions.','Alternative releases tuned to Melbourne after-dark energy.',2023,4918,'images/artists/harbor-study-avatar.svg','images/artists/harbor-study-hero.svg',6,5,3);
INSERT INTO "artists" VALUES(28,'Street Lantern','street-lantern','Sao Paulo, Brazil','Street Lantern operate inside the Sao Paulo scene, shaping rock records that favor texture, place, and carefully staged physical editions.','Rock releases tuned to Sao Paulo after-dark energy.',2015,5061,'images/artists/street-lantern-avatar.svg','images/artists/street-lantern-hero.svg',7,6,4);
INSERT INTO "artists" VALUES(29,'Noon Frame','noon-frame','Detroit, United States','Noon Frame operate inside the Detroit scene, shaping ambient records that favor texture, place, and carefully staged physical editions.','Ambient releases tuned to Detroit after-dark energy.',2016,5204,'images/artists/noon-frame-avatar.svg','images/artists/noon-frame-hero.svg',8,7,5);
INSERT INTO "artists" VALUES(30,'Low Atlas','low-atlas','Paris, France','Low Atlas operate inside the Paris scene, shaping hip-hop/rap records that favor texture, place, and carefully staged physical editions.','Hip-Hop/Rap releases tuned to Paris after-dark energy.',2017,5347,'images/artists/low-atlas-avatar.svg','images/artists/low-atlas-hero.svg',9,8,6);
INSERT INTO "artists" VALUES(31,'Chrome Willow','chrome-willow','Los Angeles, United States','Chrome Willow operate inside the Los Angeles scene, shaping metal records that favor texture, place, and carefully staged physical editions.','Metal releases tuned to Los Angeles after-dark energy.',2018,5490,'images/artists/chrome-willow-avatar.svg','images/artists/chrome-willow-hero.svg',1,9,7);
INSERT INTO "artists" VALUES(32,'Radio Meadow','radio-meadow','Berlin, Germany','Radio Meadow operate inside the Berlin scene, shaping punk records that favor texture, place, and carefully staged physical editions.','Punk releases tuned to Berlin after-dark energy.',2019,5633,'images/artists/radio-meadow-avatar.svg','images/artists/radio-meadow-hero.svg',2,10,8);
INSERT INTO "artists" VALUES(33,'Fault Parade','fault-parade','Tokyo, Japan','Fault Parade operate inside the Tokyo scene, shaping jazz records that favor texture, place, and carefully staged physical editions.','Jazz releases tuned to Tokyo after-dark energy.',2020,5776,'images/artists/fault-parade-avatar.svg','images/artists/fault-parade-hero.svg',3,1,9);
INSERT INTO "artists" VALUES(34,'Static Ledger','static-ledger','London, United Kingdom','Static Ledger operate inside the London scene, shaping folk records that favor texture, place, and carefully staged physical editions.','Folk releases tuned to London after-dark energy.',2021,5919,'images/artists/static-ledger-avatar.svg','images/artists/static-ledger-hero.svg',4,2,10);
INSERT INTO "artists" VALUES(35,'Stone Balcony','stone-balcony','New York, United States','Stone Balcony operate inside the New York scene, shaping pop records that favor texture, place, and carefully staged physical editions.','Pop releases tuned to New York after-dark energy.',2022,6062,'images/artists/stone-balcony-avatar.svg','images/artists/stone-balcony-hero.svg',5,3,11);
INSERT INTO "artists" VALUES(36,'West Transit','west-transit','Melbourne, Australia','West Transit operate inside the Melbourne scene, shaping techno records that favor texture, place, and carefully staged physical editions.','Techno releases tuned to Melbourne after-dark energy.',2023,6205,'images/artists/west-transit-avatar.svg','images/artists/west-transit-hero.svg',6,4,12);
INSERT INTO "artists" VALUES(37,'Echo Dividend','echo-dividend','Sao Paulo, Brazil','Echo Dividend operate inside the Sao Paulo scene, shaping electronic records that favor texture, place, and carefully staged physical editions.','Electronic releases tuned to Sao Paulo after-dark energy.',2015,6348,'images/artists/echo-dividend-avatar.svg','images/artists/echo-dividend-hero.svg',7,5,1);
INSERT INTO "artists" VALUES(38,'Cloud Bureau','cloud-bureau','Detroit, United States','Cloud Bureau operate inside the Detroit scene, shaping experimental records that favor texture, place, and carefully staged physical editions.','Experimental releases tuned to Detroit after-dark energy.',2016,6491,'images/artists/cloud-bureau-avatar.svg','images/artists/cloud-bureau-hero.svg',8,6,2);
INSERT INTO "artists" VALUES(39,'Ridge Cinema','ridge-cinema','Paris, France','Ridge Cinema operate inside the Paris scene, shaping alternative records that favor texture, place, and carefully staged physical editions.','Alternative releases tuned to Paris after-dark energy.',2017,6634,'images/artists/ridge-cinema-avatar.svg','images/artists/ridge-cinema-hero.svg',9,7,3);
INSERT INTO "artists" VALUES(40,'Hollow Method','hollow-method','Los Angeles, United States','Hollow Method operate inside the Los Angeles scene, shaping rock records that favor texture, place, and carefully staged physical editions.','Rock releases tuned to Los Angeles after-dark energy.',2018,6777,'images/artists/hollow-method-avatar.svg','images/artists/hollow-method-hero.svg',1,8,4);
CREATE TABLE cart_items (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	album_id INTEGER, 
	merch_item_id INTEGER, 
	format_variant_id INTEGER, 
	quantity INTEGER, 
	added_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(merch_item_id) REFERENCES merch_items (id), 
	FOREIGN KEY(format_variant_id) REFERENCES format_variants (id)
);
INSERT INTO "cart_items" VALUES(1,1,1,NULL,2,1,'2026-05-27 10:33:29.724432');
INSERT INTO "cart_items" VALUES(2,1,7,NULL,35,1,'2026-05-27 10:33:29.725265');
INSERT INTO "cart_items" VALUES(3,1,NULL,1,8,1,'2026-05-27 10:33:29.727873');
INSERT INTO "cart_items" VALUES(4,2,11,NULL,55,1,'2026-05-27 10:33:29.728486');
INSERT INTO "cart_items" VALUES(5,2,NULL,11,60,1,'2026-05-27 10:33:29.729074');
INSERT INTO "cart_items" VALUES(6,3,15,NULL,74,1,'2026-05-27 10:33:29.729657');
INSERT INTO "cart_items" VALUES(7,3,NULL,7,41,1,'2026-05-27 10:33:29.730503');
INSERT INTO "cart_items" VALUES(8,4,NULL,15,79,1,'2026-05-27 10:33:29.731346');
INSERT INTO "cart_items" VALUES(9,4,19,NULL,97,1,'2026-05-27 10:33:29.731901');
CREATE TABLE fan_collection_items (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	album_id INTEGER NOT NULL, 
	format_variant_id INTEGER, 
	favorite_track_id INTEGER, 
	acquired_via VARCHAR(80), 
	notes VARCHAR(240), 
	added_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(format_variant_id) REFERENCES format_variants (id), 
	FOREIGN KEY(favorite_track_id) REFERENCES tracks (id)
);
INSERT INTO "fan_collection_items" VALUES(1,1,13,64,63,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
INSERT INTO "fan_collection_items" VALUES(2,1,1,1,3,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
INSERT INTO "fan_collection_items" VALUES(3,2,11,55,53,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
INSERT INTO "fan_collection_items" VALUES(4,2,21,108,103,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
INSERT INTO "fan_collection_items" VALUES(5,3,7,35,33,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
INSERT INTO "fan_collection_items" VALUES(6,4,19,97,93,'purchase','Seeded library item','2026-05-01 12:00:00.000000');
CREATE TABLE fan_comments (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	album_id INTEGER, 
	track_id INTEGER, 
	headline VARCHAR(140), 
	body TEXT, 
	rating INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(track_id) REFERENCES tracks (id)
);
INSERT INTO "fan_comments" VALUES(1,1,1,NULL,'Most replayed this month','The dub bassline on side B makes the whole release feel tidal.',5,'2026-04-29 12:00:00.000000');
INSERT INTO "fan_comments" VALUES(2,2,11,NULL,'Sharp sequencing','Track order is ruthless in the best possible way.',5,'2026-04-29 12:00:00.000000');
INSERT INTO "fan_comments" VALUES(3,3,7,NULL,'Commuter ambient','Feels like catching the last Yamanote line with the windows fogged over.',5,'2026-04-29 12:00:00.000000');
INSERT INTO "fan_comments" VALUES(4,4,15,NULL,'Warm and tactile','The lyric sheet tucked into the LP package is a lovely touch.',5,'2026-04-29 12:00:00.000000');
CREATE TABLE format_variants (
	id INTEGER NOT NULL, 
	album_id INTEGER, 
	merch_item_id INTEGER, 
	kind VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	option_a VARCHAR(80), 
	option_b VARCHAR(80), 
	price FLOAT, 
	inventory INTEGER, 
	sku VARCHAR(80) NOT NULL, 
	shipping_note VARCHAR(160), 
	edition_note VARCHAR(200), 
	is_default BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(merch_item_id) REFERENCES merch_items (id), 
	UNIQUE (sku)
);
INSERT INTO "format_variants" VALUES(1,1,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'tidal-memory-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(2,1,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,42,'tidal-memory-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(3,1,NULL,'cassette','Cassette','Transparent Shell','',15.0,28,'tidal-memory-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(4,2,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'night-ferry-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(5,2,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',22.5,42,'night-ferry-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(6,2,NULL,'cassette','Cassette','Transparent Shell','',13.5,28,'night-ferry-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(7,NULL,1,'shirt','Studio Tee','S','Washed Navy',32.0,19,'neon-harbor-studio-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(8,NULL,1,'shirt','Studio Tee','M','Washed Navy',32.0,20,'neon-harbor-studio-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(9,NULL,1,'shirt','Studio Tee','L','Washed Navy',32.0,21,'neon-harbor-studio-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(10,NULL,1,'shirt','Studio Tee','XL','Washed Navy',32.0,22,'neon-harbor-studio-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(11,NULL,2,'slipmat','Pair','12-inch','',24.0,20,'neon-harbor-breakwater-slipmat-slipmat-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(12,NULL,2,'slipmat','Deluxe Pair','Glow Edge','',29.0,21,'neon-harbor-breakwater-slipmat-slipmat-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(13,3,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'static-bloom-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(14,3,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,43,'static-bloom-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(15,3,NULL,'cd','Compact Disc','Gatefold','',17.0,35,'static-bloom-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(16,4,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'paper-signal-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(17,4,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,43,'paper-signal-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(18,4,NULL,'cd','Compact Disc','Gatefold','',16.0,35,'paper-signal-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(19,NULL,3,'shirt','Stairwell Tee','S','Heather Grey',30.0,20,'glass-choir-stairwell-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(20,NULL,3,'shirt','Stairwell Tee','M','Heather Grey',30.0,21,'glass-choir-stairwell-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(21,NULL,3,'shirt','Stairwell Tee','L','Heather Grey',30.0,22,'glass-choir-stairwell-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(22,NULL,3,'shirt','Stairwell Tee','XL','Heather Grey',30.0,23,'glass-choir-stairwell-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(23,NULL,4,'poster','Standard','18x24','',18.0,21,'glass-choir-balcony-poster-poster-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(24,NULL,4,'poster','Signed','18x24','',24.0,22,'glass-choir-balcony-poster-poster-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(25,5,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'redline-ritual-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(26,5,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,44,'redline-ritual-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(27,6,NULL,'digital','Digital Album','MP3 + FLAC','',9.5,9999,'machine-prayer-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(28,6,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',25.0,44,'machine-prayer-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(29,NULL,5,'slipmat','Pair','12-inch','',22.0,21,'ashen-circuit-grid-slipmat-slipmat-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(30,NULL,5,'slipmat','Glow Pair','12-inch','',27.0,22,'ashen-circuit-grid-slipmat-slipmat-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(31,NULL,6,'patch','Standard','Black','',10.0,22,'ashen-circuit-weld-patch-patch-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(32,NULL,6,'patch','Reflective','Silver','',13.0,23,'ashen-circuit-weld-patch-patch-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(33,7,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'between-stations-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(34,7,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,45,'between-stations-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(35,7,NULL,'cassette','Cassette','Transparent Shell','',14.5,31,'between-stations-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(36,8,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'sleep-maps-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(37,8,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,45,'sleep-maps-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(38,8,NULL,'cassette','Cassette','Transparent Shell','',14.0,31,'sleep-maps-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(39,NULL,7,'hoodie','Drift Hoodie','S','Stone',48.0,22,'soft-locale-drift-hoodie-hoodie-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(40,NULL,7,'hoodie','Drift Hoodie','M','Stone',48.0,23,'soft-locale-drift-hoodie-hoodie-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(41,NULL,7,'hoodie','Drift Hoodie','L','Stone',48.0,24,'soft-locale-drift-hoodie-hoodie-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(42,NULL,7,'hoodie','Drift Hoodie','XL','Stone',48.0,25,'soft-locale-drift-hoodie-hoodie-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(43,NULL,8,'cassette','Blue Shell','Numbered','',26.0,23,'soft-locale-rain-map-cassette-box-cassette-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(44,NULL,8,'cassette','Smoke Shell','Numbered','',29.0,24,'soft-locale-rain-map-cassette-box-cassette-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(45,9,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'concrete-carnival-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(46,9,NULL,'cassette','Cassette','Transparent Shell','',14.0,32,'concrete-carnival-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(47,10,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'siren-economy-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(48,10,NULL,'cassette','Cassette','Transparent Shell','',13.5,32,'siren-economy-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(49,NULL,9,'shirt','Flyer Tee','S','White',28.0,23,'south-exit-flyer-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(50,NULL,9,'shirt','Flyer Tee','M','White',28.0,24,'south-exit-flyer-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(51,NULL,9,'shirt','Flyer Tee','L','White',28.0,25,'south-exit-flyer-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(52,NULL,9,'shirt','Flyer Tee','XL','White',28.0,26,'south-exit-flyer-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(53,NULL,10,'poster','3-Pack','18x24','',16.0,24,'south-exit-poster-pack-poster-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(54,NULL,10,'poster','Signed 3-Pack','18x24','',22.0,25,'south-exit-poster-pack-poster-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(55,11,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'signal-debt-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(56,11,NULL,'cassette','Cassette','Transparent Shell','',15.0,33,'signal-debt-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(57,12,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'blueprint-fever-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(58,12,NULL,'cassette','Cassette','Transparent Shell','',14.5,33,'blueprint-fever-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(59,NULL,11,'poster','Standard','18x24','',20.0,24,'cinder-plaza-blueprint-fever-poster-poster-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(60,NULL,11,'poster','Signed','18x24','',28.0,25,'cinder-plaza-blueprint-fever-poster-poster-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(61,NULL,12,'cap','Adjustable','Black','',26.0,25,'cinder-plaza-signal-debt-cap-cap-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(62,NULL,12,'cap','Adjustable','Sand','',26.0,26,'cinder-plaza-signal-debt-cap-cap-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(63,13,NULL,'digital','Digital Album','MP3 + FLAC','',9.5,9999,'blue-hour-broadcast-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(64,13,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',25.0,48,'blue-hour-broadcast-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(65,13,NULL,'cd','Compact Disc','Gatefold','',17.5,40,'blue-hour-broadcast-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(66,14,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'lobby-mirage-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(67,14,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,48,'lobby-mirage-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(68,14,NULL,'cd','Compact Disc','Gatefold','',16.0,40,'lobby-mirage-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(69,NULL,13,'poster','Standard','18x24','',19.0,25,'velvet-avenue-night-shift-poster-poster-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(70,NULL,13,'poster','Signed','18x24','',27.0,26,'velvet-avenue-night-shift-poster-poster-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(71,NULL,14,'tote','Setlist Tote','Natural','',24.0,26,'velvet-avenue-setlist-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(72,NULL,14,'tote','Setlist Tote','Black','',24.0,27,'velvet-avenue-setlist-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(73,15,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'riverlights-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(74,15,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,49,'riverlights-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(75,15,NULL,'cassette','Cassette','Transparent Shell','',14.5,35,'riverlights-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(76,16,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'common-thread-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(77,16,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,49,'common-thread-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(78,16,NULL,'cassette','Cassette','Transparent Shell','',14.0,35,'common-thread-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(79,NULL,15,'tote','Field Notes Tote','Natural','',22.0,26,'salt-meadow-field-notes-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(80,NULL,15,'tote','Field Notes Tote','Forest','',22.0,27,'salt-meadow-field-notes-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(81,NULL,16,'zine','Issue One','Stapled','',14.0,27,'salt-meadow-riverlights-lyric-zine-zine-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(82,NULL,16,'zine','Signed Issue','Stapled','',18.0,28,'salt-meadow-riverlights-lyric-zine-zine-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(83,17,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'iron-sleep-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(84,17,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,50,'iron-sleep-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(85,17,NULL,'cd','Compact Disc','Gatefold','',17.0,42,'iron-sleep-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(86,18,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'saint-of-noise-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(87,18,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,50,'saint-of-noise-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(88,18,NULL,'cd','Compact Disc','Gatefold','',16.5,42,'saint-of-noise-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(89,NULL,17,'shirt','Longsleeve','S','Black',36.0,27,'iron-veil-chapel-longsleeve-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(90,NULL,17,'shirt','Longsleeve','M','Black',36.0,28,'iron-veil-chapel-longsleeve-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(91,NULL,17,'shirt','Longsleeve','L','Black',36.0,29,'iron-veil-chapel-longsleeve-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(92,NULL,17,'shirt','Longsleeve','XL','Black',36.0,30,'iron-veil-chapel-longsleeve-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(93,NULL,18,'patch','3-Pack','Silver Edge','',12.0,28,'iron-veil-noise-patch-set-patch-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(94,NULL,18,'patch','3-Pack Deluxe','Glow Edge','',16.0,29,'iron-veil-noise-patch-set-patch-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(95,19,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'elastic-hearts-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(96,19,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,51,'elastic-hearts-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(97,19,NULL,'cd','Compact Disc','Gatefold','',17.0,43,'elastic-hearts-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(98,20,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'mirror-mosaic-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(99,20,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,51,'mirror-mosaic-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(100,20,NULL,'cd','Compact Disc','Gatefold','',16.0,43,'mirror-mosaic-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(101,NULL,19,'shirt','Gloss Tee','S','White',29.0,28,'fever-arcade-gloss-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(102,NULL,19,'shirt','Gloss Tee','M','White',29.0,29,'fever-arcade-gloss-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(103,NULL,19,'shirt','Gloss Tee','L','White',29.0,30,'fever-arcade-gloss-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(104,NULL,19,'shirt','Gloss Tee','XL','White',29.0,31,'fever-arcade-gloss-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(105,NULL,20,'pin','2-Pin Set','Chrome','',15.0,29,'fever-arcade-mirror-pin-set-pin-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(106,NULL,20,'pin','2-Pin Set','Rose','',15.0,30,'fever-arcade-mirror-pin-set-pin-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(107,21,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'resin-language-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(108,21,NULL,'cassette','Cassette','Transparent Shell','',15.0,38,'resin-language-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(109,22,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'fault-choir-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(110,22,NULL,'cassette','Cassette','Transparent Shell','',14.5,38,'fault-choir-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(111,NULL,21,'zine','Issue One','Stapled','',13.0,29,'mono-shrine-fault-choir-zine-zine-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(112,NULL,21,'zine','Bundle','With Sticker Sheet','',17.0,30,'mono-shrine-fault-choir-zine-zine-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(113,NULL,22,'poster','Standard','A2','',17.0,30,'mono-shrine-resin-poster-poster-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(114,NULL,22,'poster','Signed','A2','',23.0,31,'mono-shrine-resin-poster-poster-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(115,23,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'harbor-burn-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(116,23,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,53,'harbor-burn-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(117,23,NULL,'cd','Compact Disc','Gatefold','',16.0,45,'harbor-burn-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(118,24,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'quiet-engine-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(119,24,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,53,'quiet-engine-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(120,24,NULL,'cd','Compact Disc','Gatefold','',15.5,45,'quiet-engine-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(121,NULL,23,'shirt','Burn Tee','S','Vintage White',30.0,30,'tide-static-burn-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(122,NULL,23,'shirt','Burn Tee','M','Vintage White',30.0,31,'tide-static-burn-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(123,NULL,23,'shirt','Burn Tee','L','Vintage White',30.0,32,'tide-static-burn-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(124,NULL,23,'shirt','Burn Tee','XL','Vintage White',30.0,33,'tide-static-burn-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(125,NULL,24,'tote','Engine Tote','Natural','',21.0,31,'tide-static-quiet-engine-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(126,NULL,24,'tote','Engine Tote','Black','',21.0,32,'tide-static-quiet-engine-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(127,25,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'static-weather-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(128,25,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',22.5,54,'static-weather-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(129,25,NULL,'cassette','Cassette','Transparent Shell','',13.5,40,'static-weather-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(130,26,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'quiet-vector-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(131,26,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,54,'quiet-vector-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(132,26,NULL,'cassette','Cassette','Transparent Shell','',14.0,40,'quiet-vector-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(133,NULL,25,'shirt','Tour Tee','S','Black',29.0,31,'amber-relay-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(134,NULL,25,'shirt','Tour Tee','M','Black',29.0,32,'amber-relay-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(135,NULL,25,'shirt','Tour Tee','L','Black',29.0,33,'amber-relay-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(136,NULL,25,'shirt','Tour Tee','XL','Black',29.0,34,'amber-relay-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(137,NULL,26,'tote','Carry Tote','Natural','',21.0,32,'amber-relay-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(138,NULL,26,'tote','Carry Tote','Black','',21.0,33,'amber-relay-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(139,27,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'harbor-ledger-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(140,27,NULL,'cassette','Cassette','Transparent Shell','',14.0,41,'harbor-ledger-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(141,28,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'paper-thread-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(142,28,NULL,'cassette','Cassette','Transparent Shell','',14.5,41,'paper-thread-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(143,NULL,27,'shirt','Tour Tee','S','Black',30.0,32,'paper-current-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(144,NULL,27,'shirt','Tour Tee','M','Black',30.0,33,'paper-current-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(145,NULL,27,'shirt','Tour Tee','L','Black',30.0,34,'paper-current-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(146,NULL,27,'shirt','Tour Tee','XL','Black',30.0,35,'paper-current-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(147,NULL,28,'tote','Carry Tote','Natural','',22.0,33,'paper-current-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(148,NULL,28,'tote','Carry Tote','Black','',22.0,34,'paper-current-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(149,29,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'river-cinema-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(150,29,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,56,'river-cinema-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(151,29,NULL,'cd','Compact Disc','Gatefold','',16.0,48,'river-cinema-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(152,30,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'chrome-parade-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(153,30,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,56,'chrome-parade-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(154,30,NULL,'cd','Compact Disc','Gatefold','',16.5,48,'chrome-parade-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(155,NULL,29,'shirt','Tour Tee','S','Black',31.0,33,'silver-weather-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(156,NULL,29,'shirt','Tour Tee','M','Black',31.0,34,'silver-weather-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(157,NULL,29,'shirt','Tour Tee','L','Black',31.0,35,'silver-weather-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(158,NULL,29,'shirt','Tour Tee','XL','Black',31.0,36,'silver-weather-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(159,NULL,30,'tote','Carry Tote','Natural','',23.0,34,'silver-weather-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(160,NULL,30,'tote','Carry Tote','Black','',23.0,35,'silver-weather-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(161,31,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'signal-method-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(162,31,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,57,'signal-method-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(163,31,NULL,'cd','Compact Disc','Gatefold','',16.5,49,'signal-method-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(164,32,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'south-engine-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(165,32,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,57,'south-engine-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(166,32,NULL,'cd','Compact Disc','Gatefold','',17.0,49,'south-engine-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(167,NULL,31,'shirt','Tour Tee','S','Black',32.0,34,'north-routine-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(168,NULL,31,'shirt','Tour Tee','M','Black',32.0,35,'north-routine-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(169,NULL,31,'shirt','Tour Tee','L','Black',32.0,36,'north-routine-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(170,NULL,31,'shirt','Tour Tee','XL','Black',32.0,37,'north-routine-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(171,NULL,32,'tote','Carry Tote','Natural','',21.0,35,'north-routine-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(172,NULL,32,'tote','Carry Tote','Black','',21.0,36,'north-routine-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(173,33,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'blue-current-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(174,33,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,58,'blue-current-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(175,33,NULL,'cassette','Cassette','Transparent Shell','',15.5,44,'blue-current-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(176,34,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'midnight-signal-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(177,34,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,58,'midnight-signal-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(178,34,NULL,'cassette','Cassette','Transparent Shell','',14.0,44,'midnight-signal-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(179,NULL,33,'shirt','Tour Tee','S','Black',29.0,35,'copper-bloom-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(180,NULL,33,'shirt','Tour Tee','M','Black',29.0,36,'copper-bloom-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(181,NULL,33,'shirt','Tour Tee','L','Black',29.0,37,'copper-bloom-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(182,NULL,33,'shirt','Tour Tee','XL','Black',29.0,38,'copper-bloom-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(183,NULL,34,'tote','Carry Tote','Natural','',22.0,36,'copper-bloom-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(184,NULL,34,'tote','Carry Tote','Black','',22.0,37,'copper-bloom-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(185,35,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'late-boulevard-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(186,35,NULL,'cassette','Cassette','Transparent Shell','',13.5,45,'late-boulevard-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(187,36,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'glass-mosaic-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(188,36,NULL,'cassette','Cassette','Transparent Shell','',14.5,45,'glass-mosaic-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(189,NULL,35,'shirt','Tour Tee','S','Black',30.0,36,'ladder-choir-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(190,NULL,35,'shirt','Tour Tee','M','Black',30.0,37,'ladder-choir-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(191,NULL,35,'shirt','Tour Tee','L','Black',30.0,38,'ladder-choir-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(192,NULL,35,'shirt','Tour Tee','XL','Black',30.0,39,'ladder-choir-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(193,NULL,36,'tote','Carry Tote','Natural','',23.0,37,'ladder-choir-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(194,NULL,36,'tote','Carry Tote','Black','',23.0,38,'ladder-choir-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(195,37,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'golden-garden-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(196,37,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,60,'golden-garden-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(197,37,NULL,'cd','Compact Disc','Gatefold','',15.5,35,'golden-garden-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(198,38,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'motel-harbor-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(199,38,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,60,'motel-harbor-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(200,38,NULL,'cd','Compact Disc','Gatefold','',16.5,35,'motel-harbor-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(201,NULL,37,'shirt','Tour Tee','S','Black',31.0,37,'hour-motel-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(202,NULL,37,'shirt','Tour Tee','M','Black',31.0,38,'hour-motel-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(203,NULL,37,'shirt','Tour Tee','L','Black',31.0,39,'hour-motel-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(204,NULL,37,'shirt','Tour Tee','XL','Black',31.0,40,'hour-motel-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(205,NULL,38,'tote','Carry Tote','Natural','',21.0,38,'hour-motel-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(206,NULL,38,'tote','Carry Tote','Black','',21.0,39,'hour-motel-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(207,39,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'quiet-transit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(208,39,NULL,'cassette','Cassette','Transparent Shell','',14.5,47,'quiet-transit-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(209,40,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'stone-circuit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(210,40,NULL,'cassette','Cassette','Transparent Shell','',15.5,47,'stone-circuit-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(211,NULL,39,'shirt','Tour Tee','S','Black',32.0,38,'signal-lake-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(212,NULL,39,'shirt','Tour Tee','M','Black',32.0,39,'signal-lake-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(213,NULL,39,'shirt','Tour Tee','L','Black',32.0,40,'signal-lake-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(214,NULL,39,'shirt','Tour Tee','XL','Black',32.0,41,'signal-lake-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(215,NULL,40,'tote','Carry Tote','Natural','',22.0,39,'signal-lake-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(216,NULL,40,'tote','Carry Tote','Black','',22.0,40,'signal-lake-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(217,41,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'paper-archive-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(218,41,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,62,'paper-archive-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(219,41,NULL,'cd','Compact Disc','Gatefold','',16.5,37,'paper-archive-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(220,42,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'delta-minutes-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(221,42,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,62,'delta-minutes-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(222,42,NULL,'cd','Compact Disc','Gatefold','',15.5,37,'delta-minutes-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(223,NULL,41,'shirt','Tour Tee','S','Black',29.0,39,'delta-hall-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(224,NULL,41,'shirt','Tour Tee','M','Black',29.0,40,'delta-hall-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(225,NULL,41,'shirt','Tour Tee','L','Black',29.0,41,'delta-hall-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(226,NULL,41,'shirt','Tour Tee','XL','Black',29.0,18,'delta-hall-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(227,NULL,42,'tote','Carry Tote','Natural','',23.0,40,'delta-hall-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(228,NULL,42,'tote','Carry Tote','Black','',23.0,41,'delta-hall-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(229,43,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'chrome-pattern-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(230,43,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,63,'chrome-pattern-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(231,43,NULL,'cassette','Cassette','Transparent Shell','',15.5,28,'chrome-pattern-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(232,44,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'velvet-weather-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(233,44,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,63,'velvet-weather-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(234,44,NULL,'cassette','Cassette','Transparent Shell','',14.5,28,'velvet-weather-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(235,NULL,43,'shirt','Tour Tee','S','Black',30.0,40,'mirror-union-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(236,NULL,43,'shirt','Tour Tee','M','Black',30.0,41,'mirror-union-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(237,NULL,43,'shirt','Tour Tee','L','Black',30.0,18,'mirror-union-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(238,NULL,43,'shirt','Tour Tee','XL','Black',30.0,19,'mirror-union-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(239,NULL,44,'tote','Carry Tote','Natural','',21.0,41,'mirror-union-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(240,NULL,44,'tote','Carry Tote','Black','',21.0,18,'mirror-union-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(241,45,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'south-dusk-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(242,45,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',22.5,64,'south-dusk-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(243,45,NULL,'cd','Compact Disc','Gatefold','',15.0,39,'south-dusk-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(244,46,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'open-ledger-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(245,46,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,64,'open-ledger-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(246,46,NULL,'cd','Compact Disc','Gatefold','',16.5,39,'open-ledger-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(247,NULL,45,'shirt','Tour Tee','S','Black',31.0,41,'quiet-metric-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(248,NULL,45,'shirt','Tour Tee','M','Black',31.0,18,'quiet-metric-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(249,NULL,45,'shirt','Tour Tee','L','Black',31.0,19,'quiet-metric-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(250,NULL,45,'shirt','Tour Tee','XL','Black',31.0,20,'quiet-metric-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(251,NULL,46,'tote','Carry Tote','Natural','',22.0,18,'quiet-metric-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(252,NULL,46,'tote','Carry Tote','Black','',22.0,19,'quiet-metric-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(253,47,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'midnight-vector-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(254,47,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,65,'midnight-vector-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(255,48,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'after-cinema-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(256,48,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,65,'after-cinema-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(257,NULL,47,'shirt','Tour Tee','S','Black',32.0,18,'blue-archive-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(258,NULL,47,'shirt','Tour Tee','M','Black',32.0,19,'blue-archive-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(259,NULL,47,'shirt','Tour Tee','L','Black',32.0,20,'blue-archive-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(260,NULL,47,'shirt','Tour Tee','XL','Black',32.0,21,'blue-archive-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(261,NULL,48,'tote','Carry Tote','Natural','',23.0,19,'blue-archive-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(262,NULL,48,'tote','Carry Tote','Black','',23.0,20,'blue-archive-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(263,49,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'glass-thread-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(264,49,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,66,'glass-thread-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(265,49,NULL,'cassette','Cassette','Transparent Shell','',14.5,31,'glass-thread-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(266,50,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'broken-method-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(267,50,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,66,'broken-method-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(268,50,NULL,'cassette','Cassette','Transparent Shell','',14.0,31,'broken-method-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(269,NULL,49,'shirt','Tour Tee','S','Black',29.0,19,'stair-pattern-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(270,NULL,49,'shirt','Tour Tee','M','Black',29.0,20,'stair-pattern-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(271,NULL,49,'shirt','Tour Tee','L','Black',29.0,21,'stair-pattern-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(272,NULL,49,'shirt','Tour Tee','XL','Black',29.0,22,'stair-pattern-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(273,NULL,50,'tote','Carry Tote','Natural','',21.0,20,'stair-pattern-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(274,NULL,50,'tote','Carry Tote','Black','',21.0,21,'stair-pattern-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(275,51,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'motel-parade-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(276,51,NULL,'cassette','Cassette','Transparent Shell','',15.0,32,'motel-parade-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(277,52,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'static-current-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(278,52,NULL,'cassette','Cassette','Transparent Shell','',14.5,32,'static-current-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(279,NULL,51,'shirt','Tour Tee','S','Black',30.0,20,'velvet-current-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(280,NULL,51,'shirt','Tour Tee','M','Black',30.0,21,'velvet-current-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(281,NULL,51,'shirt','Tour Tee','L','Black',30.0,22,'velvet-current-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(282,NULL,51,'shirt','Tour Tee','XL','Black',30.0,23,'velvet-current-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(283,NULL,52,'tote','Carry Tote','Natural','',22.0,21,'velvet-current-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(284,NULL,52,'tote','Carry Tote','Black','',22.0,22,'velvet-current-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(285,53,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'stone-engine-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(286,53,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,68,'stone-engine-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(287,53,NULL,'cd','Compact Disc','Gatefold','',17.0,43,'stone-engine-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(288,54,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'harbor-boulevard-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(289,54,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,68,'harbor-boulevard-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(290,54,NULL,'cd','Compact Disc','Gatefold','',16.5,43,'harbor-boulevard-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(291,NULL,53,'shirt','Tour Tee','S','Black',31.0,21,'harbor-study-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(292,NULL,53,'shirt','Tour Tee','M','Black',31.0,22,'harbor-study-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(293,NULL,53,'shirt','Tour Tee','L','Black',31.0,23,'harbor-study-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(294,NULL,53,'shirt','Tour Tee','XL','Black',31.0,24,'harbor-study-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(295,NULL,54,'tote','Carry Tote','Natural','',23.0,22,'harbor-study-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(296,NULL,54,'tote','Carry Tote','Black','',23.0,23,'harbor-study-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(297,55,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'delta-signal-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(298,55,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',22.5,69,'delta-signal-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(299,55,NULL,'cd','Compact Disc','Gatefold','',15.0,44,'delta-signal-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(300,56,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'river-garden-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(301,56,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,69,'river-garden-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(302,56,NULL,'cd','Compact Disc','Gatefold','',17.0,44,'river-garden-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(303,NULL,55,'shirt','Tour Tee','S','Black',32.0,22,'street-lantern-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(304,NULL,55,'shirt','Tour Tee','M','Black',32.0,23,'street-lantern-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(305,NULL,55,'shirt','Tour Tee','L','Black',32.0,24,'street-lantern-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(306,NULL,55,'shirt','Tour Tee','XL','Black',32.0,25,'street-lantern-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(307,NULL,56,'tote','Carry Tote','Natural','',21.0,23,'street-lantern-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(308,NULL,56,'tote','Carry Tote','Black','',21.0,24,'street-lantern-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(309,57,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'velvet-mosaic-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(310,57,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,70,'velvet-mosaic-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(311,57,NULL,'cassette','Cassette','Transparent Shell','',14.0,35,'velvet-mosaic-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(312,58,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'signal-transit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(313,58,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,70,'signal-transit-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(314,58,NULL,'cassette','Cassette','Transparent Shell','',14.0,35,'signal-transit-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(315,NULL,57,'shirt','Tour Tee','S','Black',29.0,23,'noon-frame-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(316,NULL,57,'shirt','Tour Tee','M','Black',29.0,24,'noon-frame-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(317,NULL,57,'shirt','Tour Tee','L','Black',29.0,25,'noon-frame-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(318,NULL,57,'shirt','Tour Tee','XL','Black',29.0,26,'noon-frame-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(319,NULL,58,'tote','Carry Tote','Natural','',22.0,24,'noon-frame-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(320,NULL,58,'tote','Carry Tote','Black','',22.0,25,'noon-frame-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(321,59,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'open-harbor-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(322,59,NULL,'cassette','Cassette','Transparent Shell','',14.5,36,'open-harbor-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(323,60,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'blue-archive-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(324,60,NULL,'cassette','Cassette','Transparent Shell','',14.5,36,'blue-archive-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(325,NULL,59,'shirt','Tour Tee','S','Black',30.0,24,'low-atlas-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(326,NULL,59,'shirt','Tour Tee','M','Black',30.0,25,'low-atlas-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(327,NULL,59,'shirt','Tour Tee','L','Black',30.0,26,'low-atlas-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(328,NULL,59,'shirt','Tour Tee','XL','Black',30.0,27,'low-atlas-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(329,NULL,60,'tote','Carry Tote','Natural','',23.0,25,'low-atlas-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(330,NULL,60,'tote','Carry Tote','Black','',23.0,26,'low-atlas-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(331,61,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'after-circuit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(332,61,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,72,'after-circuit-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(333,61,NULL,'cd','Compact Disc','Gatefold','',16.5,47,'after-circuit-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(334,62,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'late-pattern-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(335,62,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,72,'late-pattern-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(336,62,NULL,'cd','Compact Disc','Gatefold','',16.5,47,'late-pattern-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(337,NULL,61,'shirt','Tour Tee','S','Black',31.0,25,'chrome-willow-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(338,NULL,61,'shirt','Tour Tee','M','Black',31.0,26,'chrome-willow-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(339,NULL,61,'shirt','Tour Tee','L','Black',31.0,27,'chrome-willow-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(340,NULL,61,'shirt','Tour Tee','XL','Black',31.0,28,'chrome-willow-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(341,NULL,62,'tote','Carry Tote','Natural','',21.0,26,'chrome-willow-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(342,NULL,62,'tote','Carry Tote','Black','',21.0,27,'chrome-willow-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(343,63,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'broken-minutes-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(344,63,NULL,'cassette','Cassette','Transparent Shell','',15.5,38,'broken-minutes-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(345,64,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'golden-dusk-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(346,64,NULL,'cassette','Cassette','Transparent Shell','',15.5,38,'golden-dusk-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(347,NULL,63,'shirt','Tour Tee','S','Black',32.0,26,'radio-meadow-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(348,NULL,63,'shirt','Tour Tee','M','Black',32.0,27,'radio-meadow-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(349,NULL,63,'shirt','Tour Tee','L','Black',32.0,28,'radio-meadow-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(350,NULL,63,'shirt','Tour Tee','XL','Black',32.0,29,'radio-meadow-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(351,NULL,64,'tote','Carry Tote','Natural','',22.0,27,'radio-meadow-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(352,NULL,64,'tote','Carry Tote','Black','',22.0,28,'radio-meadow-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(353,65,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'static-weather-fault-parade-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(354,65,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',22.5,74,'static-weather-fault-parade-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(355,65,NULL,'cd','Compact Disc','Gatefold','',15.0,49,'static-weather-fault-parade-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(356,66,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'quiet-vector-fault-parade-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(357,66,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,74,'quiet-vector-fault-parade-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(358,66,NULL,'cd','Compact Disc','Gatefold','',15.5,49,'quiet-vector-fault-parade-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(359,NULL,65,'shirt','Tour Tee','S','Black',29.0,27,'fault-parade-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(360,NULL,65,'shirt','Tour Tee','M','Black',29.0,28,'fault-parade-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(361,NULL,65,'shirt','Tour Tee','L','Black',29.0,29,'fault-parade-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(362,NULL,65,'shirt','Tour Tee','XL','Black',29.0,30,'fault-parade-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(363,NULL,66,'tote','Carry Tote','Natural','',23.0,28,'fault-parade-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(364,NULL,66,'tote','Carry Tote','Black','',23.0,29,'fault-parade-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(365,67,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'harbor-ledger-static-ledger-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(366,67,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,75,'harbor-ledger-static-ledger-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(367,67,NULL,'cassette','Cassette','Transparent Shell','',14.0,40,'harbor-ledger-static-ledger-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(368,68,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'paper-thread-static-ledger-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(369,68,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,75,'paper-thread-static-ledger-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(370,68,NULL,'cassette','Cassette','Transparent Shell','',14.5,40,'paper-thread-static-ledger-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(371,NULL,67,'shirt','Tour Tee','S','Black',30.0,28,'static-ledger-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(372,NULL,67,'shirt','Tour Tee','M','Black',30.0,29,'static-ledger-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(373,NULL,67,'shirt','Tour Tee','L','Black',30.0,30,'static-ledger-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(374,NULL,67,'shirt','Tour Tee','XL','Black',30.0,31,'static-ledger-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(375,NULL,68,'tote','Carry Tote','Natural','',21.0,29,'static-ledger-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(376,NULL,68,'tote','Carry Tote','Black','',21.0,30,'static-ledger-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(377,69,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'river-cinema-stone-balcony-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(378,69,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,76,'river-cinema-stone-balcony-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(379,69,NULL,'cd','Compact Disc','Gatefold','',16.0,34,'river-cinema-stone-balcony-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(380,70,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'chrome-parade-stone-balcony-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(381,70,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,76,'chrome-parade-stone-balcony-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(382,70,NULL,'cd','Compact Disc','Gatefold','',16.5,34,'chrome-parade-stone-balcony-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(383,NULL,69,'shirt','Tour Tee','S','Black',31.0,29,'stone-balcony-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(384,NULL,69,'shirt','Tour Tee','M','Black',31.0,30,'stone-balcony-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(385,NULL,69,'shirt','Tour Tee','L','Black',31.0,31,'stone-balcony-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(386,NULL,69,'shirt','Tour Tee','XL','Black',31.0,32,'stone-balcony-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(387,NULL,70,'tote','Carry Tote','Natural','',22.0,30,'stone-balcony-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(388,NULL,70,'tote','Carry Tote','Black','',22.0,31,'stone-balcony-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(389,71,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'signal-method-west-transit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(390,71,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,42,'signal-method-west-transit-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(391,72,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'south-engine-west-transit-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(392,72,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,42,'south-engine-west-transit-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(393,NULL,71,'shirt','Tour Tee','S','Black',32.0,30,'west-transit-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(394,NULL,71,'shirt','Tour Tee','M','Black',32.0,31,'west-transit-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(395,NULL,71,'shirt','Tour Tee','L','Black',32.0,32,'west-transit-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(396,NULL,71,'shirt','Tour Tee','XL','Black',32.0,33,'west-transit-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(397,NULL,72,'tote','Carry Tote','Natural','',23.0,31,'west-transit-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(398,NULL,72,'tote','Carry Tote','Black','',23.0,32,'west-transit-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(399,73,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'blue-current-echo-dividend-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(400,73,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,43,'blue-current-echo-dividend-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(401,73,NULL,'cassette','Cassette','Transparent Shell','',15.5,43,'blue-current-echo-dividend-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(402,74,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'midnight-signal-echo-dividend-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(403,74,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,43,'midnight-signal-echo-dividend-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(404,74,NULL,'cassette','Cassette','Transparent Shell','',14.0,43,'midnight-signal-echo-dividend-cassette-3','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(405,NULL,73,'shirt','Tour Tee','S','Black',29.0,31,'echo-dividend-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(406,NULL,73,'shirt','Tour Tee','M','Black',29.0,32,'echo-dividend-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(407,NULL,73,'shirt','Tour Tee','L','Black',29.0,33,'echo-dividend-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(408,NULL,73,'shirt','Tour Tee','XL','Black',29.0,34,'echo-dividend-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(409,NULL,74,'tote','Carry Tote','Natural','',21.0,32,'echo-dividend-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(410,NULL,74,'tote','Carry Tote','Black','',21.0,33,'echo-dividend-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(411,75,NULL,'digital','Digital Album','MP3 + FLAC','',7.0,9999,'late-boulevard-cloud-bureau-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(412,75,NULL,'cassette','Cassette','Transparent Shell','',13.5,44,'late-boulevard-cloud-bureau-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(413,76,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'glass-mosaic-cloud-bureau-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(414,76,NULL,'cassette','Cassette','Transparent Shell','',14.5,44,'glass-mosaic-cloud-bureau-cassette-2','Ships in 2-4 days','Numbered shell edition.',0);
INSERT INTO "format_variants" VALUES(415,NULL,75,'shirt','Tour Tee','S','Black',30.0,32,'cloud-bureau-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(416,NULL,75,'shirt','Tour Tee','M','Black',30.0,33,'cloud-bureau-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(417,NULL,75,'shirt','Tour Tee','L','Black',30.0,34,'cloud-bureau-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(418,NULL,75,'shirt','Tour Tee','XL','Black',30.0,35,'cloud-bureau-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(419,NULL,76,'tote','Carry Tote','Natural','',22.0,33,'cloud-bureau-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(420,NULL,76,'tote','Carry Tote','Black','',22.0,34,'cloud-bureau-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(421,77,NULL,'digital','Digital Album','MP3 + FLAC','',7.5,9999,'golden-garden-ridge-cinema-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(422,77,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.0,45,'golden-garden-ridge-cinema-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(423,77,NULL,'cd','Compact Disc','Gatefold','',15.5,38,'golden-garden-ridge-cinema-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(424,78,NULL,'digital','Digital Album','MP3 + FLAC','',8.5,9999,'motel-harbor-ridge-cinema-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(425,78,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.0,45,'motel-harbor-ridge-cinema-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(426,78,NULL,'cd','Compact Disc','Gatefold','',16.5,38,'motel-harbor-ridge-cinema-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(427,NULL,77,'shirt','Tour Tee','S','Black',31.0,33,'ridge-cinema-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(428,NULL,77,'shirt','Tour Tee','M','Black',31.0,34,'ridge-cinema-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(429,NULL,77,'shirt','Tour Tee','L','Black',31.0,35,'ridge-cinema-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(430,NULL,77,'shirt','Tour Tee','XL','Black',31.0,36,'ridge-cinema-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(431,NULL,78,'tote','Carry Tote','Natural','',23.0,34,'ridge-cinema-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(432,NULL,78,'tote','Carry Tote','Black','',23.0,35,'ridge-cinema-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(433,79,NULL,'digital','Digital Album','MP3 + FLAC','',8.0,9999,'quiet-transit-hollow-method-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(434,79,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',23.5,46,'quiet-transit-hollow-method-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(435,79,NULL,'cd','Compact Disc','Gatefold','',16.0,39,'quiet-transit-hollow-method-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(436,80,NULL,'digital','Digital Album','MP3 + FLAC','',9.0,9999,'stone-circuit-hollow-method-digital-1','Instant download','Unlimited streams in the mirror.',1);
INSERT INTO "format_variants" VALUES(437,80,NULL,'vinyl','Colored Vinyl','12-inch','Ocean Blue',24.5,46,'stone-circuit-hollow-method-vinyl-2','Ships in 3-5 days','Limited mirror pressing.',0);
INSERT INTO "format_variants" VALUES(438,80,NULL,'cd','Compact Disc','Gatefold','',17.0,39,'stone-circuit-hollow-method-cd-3','Ships in 2-4 days','Includes lyric foldout.',0);
INSERT INTO "format_variants" VALUES(439,NULL,79,'shirt','Tour Tee','S','Black',32.0,34,'hollow-method-tour-tee-shirt-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(440,NULL,79,'shirt','Tour Tee','M','Black',32.0,35,'hollow-method-tour-tee-shirt-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(441,NULL,79,'shirt','Tour Tee','L','Black',32.0,36,'hollow-method-tour-tee-shirt-3','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(442,NULL,79,'shirt','Tour Tee','XL','Black',32.0,37,'hollow-method-tour-tee-shirt-4','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
INSERT INTO "format_variants" VALUES(443,NULL,80,'tote','Carry Tote','Natural','',21.0,35,'hollow-method-carry-tote-tote-1','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',1);
INSERT INTO "format_variants" VALUES(444,NULL,80,'tote','Carry Tote','Black','',21.0,36,'hollow-method-carry-tote-tote-2','Ships in 2-5 days','Locally generated merch photo and deterministic variant data.',0);
CREATE TABLE genres (
	id INTEGER NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	description TEXT, 
	accent_color VARCHAR(20), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
INSERT INTO "genres" VALUES(1,'electronic','electronic','Clubs, synth architecture, and digital fog.','#0f5ea8');
INSERT INTO "genres" VALUES(2,'experimental','experimental','Boundary-pushing releases with noise, tape, and collage impulses.','#6b2fb3');
INSERT INTO "genres" VALUES(3,'alternative','alternative','Hook-heavy independent records, dream pop, and guitar shimmer.','#274ab8');
INSERT INTO "genres" VALUES(4,'rock','rock','Fuzz, motorik rhythm sections, and widescreen choruses.','#a63b34');
INSERT INTO "genres" VALUES(5,'ambient','ambient','Slow-moving drift, field recordings, and restorative detail.','#145c4b');
INSERT INTO "genres" VALUES(6,'hip-hop/rap','hip-hop-rap','Sharp lyric sheets, beat experiments, and street-level memoir.','#9333ea');
INSERT INTO "genres" VALUES(7,'metal','metal','Dense distortion, ritual percussion, and high-pressure dynamics.','#7c2d12');
INSERT INTO "genres" VALUES(8,'punk','punk','Fast, bright, political, and built for tiny rooms.','#be123c');
INSERT INTO "genres" VALUES(9,'jazz','jazz','Late-night improvisation, spiritual harmony, and room sound.','#0f766e');
INSERT INTO "genres" VALUES(10,'folk','folk','Acoustic storytelling, communal choruses, and road-worn detail.','#7c2d12');
INSERT INTO "genres" VALUES(11,'pop','pop','Polished melodies, neon hooks, and emotional lift.','#1d4ed8');
INSERT INTO "genres" VALUES(12,'techno','techno','Machine pulse, analog grit, and hypnotic low-end.','#0f5ea8');
CREATE TABLE labels (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	location VARCHAR(120), 
	description TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
INSERT INTO "labels" VALUES(1,'Aperture Tapes','aperture-tapes','Berlin, Germany','Pressings that lean toward dub techno, electro, and humid afterhours ambience.');
INSERT INTO "labels" VALUES(2,'Midnight Service','midnight-service','London, United Kingdom','Independent label focused on guitar records and night-bus pop.');
INSERT INTO "labels" VALUES(3,'Motor Relay','motor-relay','Detroit, United States','Hardware-forward dance music and disciplined machine funk.');
INSERT INTO "labels" VALUES(4,'Inland Weather','inland-weather','Tokyo, Japan','Ambient and electro-acoustic labels with carefully built physical editions.');
INSERT INTO "labels" VALUES(5,'South District','south-district','Sao Paulo, Brazil','Razor-wire punk, no-wave experiments, and scene-documentation merch.');
INSERT INTO "labels" VALUES(6,'Sun Trace','sun-trace','Los Angeles, United States','Beat music, jazz crossover, and cinematic low-end.');
INSERT INTO "labels" VALUES(7,'Night School Annex','night-school-annex','New York, United States','Jazz-leaning independents with tactile design systems.');
INSERT INTO "labels" VALUES(8,'Lantern Union','lantern-union','Melbourne, Australia','Songwriter records and small-batch merch with printshop charm.');
INSERT INTO "labels" VALUES(9,'Obsidian Bloom','obsidian-bloom','Paris, France','Heavy records with monochrome art direction and deluxe inserts.');
INSERT INTO "labels" VALUES(10,'Harbor Circuit','harbor-circuit','Global','Cross-scene collaborations curated for the mirror benchmark.');
CREATE TABLE merch_items (
	id INTEGER NOT NULL, 
	artist_id INTEGER NOT NULL, 
	album_id INTEGER, 
	title VARCHAR(160) NOT NULL, 
	slug VARCHAR(180) NOT NULL, 
	item_type VARCHAR(50), 
	description TEXT, 
	short_blurb VARCHAR(200), 
	image VARCHAR(255), 
	price FLOAT, 
	inventory INTEGER, 
	release_date DATE NOT NULL, 
	is_featured BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(artist_id) REFERENCES artists (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id)
);
INSERT INTO "merch_items" VALUES(1,1,1,'Neon Harbor Studio Tee','neon-harbor-studio-tee','shirt','Neon Harbor Studio Tee is a shirt release tied to Tidal Memory, printed locally for Neon Harbor with clean benchmark-ready variant information.','Garment-dyed heavyweight tee with the Tidal Memory mark.','images/merch/neon-harbor-studio-tee.svg',32.0,55,'2025-09-30',1);
INSERT INTO "merch_items" VALUES(2,1,2,'Neon Harbor Breakwater Slipmat','neon-harbor-breakwater-slipmat','slipmat','Neon Harbor Breakwater Slipmat is a slipmat release tied to Night Ferry, printed locally for Neon Harbor with clean benchmark-ready variant information.','Pair of felt slipmats printed with breakwater geometry.','images/merch/neon-harbor-breakwater-slipmat.svg',24.0,61,'2025-10-05',1);
INSERT INTO "merch_items" VALUES(3,2,3,'Glass Choir Stairwell Tee','glass-choir-stairwell-tee','shirt','Glass Choir Stairwell Tee is a shirt release tied to Static Bloom, printed locally for Glass Choir with clean benchmark-ready variant information.','Soft grey shirt with stairwell photo treatment.','images/merch/glass-choir-stairwell-tee.svg',30.0,57,'2026-02-06',1);
INSERT INTO "merch_items" VALUES(4,2,4,'Glass Choir Balcony Poster','glass-choir-balcony-poster','poster','Glass Choir Balcony Poster is a poster release tied to Paper Signal, printed locally for Glass Choir with clean benchmark-ready variant information.','Risograph poster pulled from the Paper Signal cover session.','images/merch/glass-choir-balcony-poster.svg',18.0,63,'2026-02-11',1);
INSERT INTO "merch_items" VALUES(5,3,6,'Ashen Circuit Grid Slipmat','ashen-circuit-grid-slipmat','slipmat','Ashen Circuit Grid Slipmat is a slipmat release tied to Machine Prayer, printed locally for Ashen Circuit with clean benchmark-ready variant information.','Dense white-on-black slipmat pair with the Machine Prayer grid.','images/merch/ashen-circuit-grid-slipmat.svg',22.0,59,'2025-05-16',1);
INSERT INTO "merch_items" VALUES(6,3,5,'Ashen Circuit Weld Patch','ashen-circuit-weld-patch','patch','Ashen Circuit Weld Patch is a patch release tied to Redline Ritual, printed locally for Ashen Circuit with clean benchmark-ready variant information.','Embroidered patch cut from the Redline Ritual symbol language.','images/merch/ashen-circuit-weld-patch.svg',10.0,65,'2025-05-21',1);
INSERT INTO "merch_items" VALUES(7,4,7,'Soft Locale Drift Hoodie','soft-locale-drift-hoodie','hoodie','Soft Locale Drift Hoodie is a hoodie release tied to Between Stations, printed locally for Soft Locale with clean benchmark-ready variant information.','Midweight hoodie with a reflective commuter-grid chest print.','images/merch/soft-locale-drift-hoodie.svg',48.0,61,'2025-07-18',1);
INSERT INTO "merch_items" VALUES(8,4,8,'Soft Locale Rain Map Cassette Box','soft-locale-rain-map-cassette-box','cassette','Soft Locale Rain Map Cassette Box is a cassette release tied to Sleep Maps, printed locally for Soft Locale with clean benchmark-ready variant information.','Cassette shell and booklet edition with a fold-out station map.','images/merch/soft-locale-rain-map-cassette-box.svg',26.0,67,'2025-07-23',1);
INSERT INTO "merch_items" VALUES(9,5,9,'South Exit Flyer Tee','south-exit-flyer-tee','shirt','South Exit Flyer Tee is a shirt release tied to Concrete Carnival, printed locally for South Exit with clean benchmark-ready variant information.','Cracked-print tee based on a xeroxed show flyer.','images/merch/south-exit-flyer-tee.svg',28.0,63,'2025-03-28',1);
INSERT INTO "merch_items" VALUES(10,5,10,'South Exit Poster Pack','south-exit-poster-pack','poster','South Exit Poster Pack is a poster release tied to Siren Economy, printed locally for South Exit with clean benchmark-ready variant information.','Three-poster bundle featuring concrete stencil variants.','images/merch/south-exit-poster-pack.svg',16.0,69,'2025-04-02',1);
INSERT INTO "merch_items" VALUES(11,6,12,'Cinder Plaza Blueprint Fever Poster','cinder-plaza-blueprint-fever-poster','poster','Cinder Plaza Blueprint Fever Poster is a poster release tied to Blueprint Fever, printed locally for Cinder Plaza with clean benchmark-ready variant information.','Blueprint grid poster with a signed edition for collectors.','images/merch/cinder-plaza-blueprint-fever-poster.svg',20.0,65,'2025-09-05',1);
INSERT INTO "merch_items" VALUES(12,6,11,'Cinder Plaza Signal Debt Cap','cinder-plaza-signal-debt-cap','cap','Cinder Plaza Signal Debt Cap is a cap release tied to Signal Debt, printed locally for Cinder Plaza with clean benchmark-ready variant information.','Low-profile cap embroidered with the Signal Debt skyline.','images/merch/cinder-plaza-signal-debt-cap.svg',26.0,71,'2025-09-10',1);
INSERT INTO "merch_items" VALUES(13,7,13,'Velvet Avenue Night Shift Poster','velvet-avenue-night-shift-poster','poster','Velvet Avenue Night Shift Poster is a poster release tied to Blue Hour Broadcast, printed locally for Velvet Avenue with clean benchmark-ready variant information.','Matte poster with the Blue Hour Broadcast room diagram.','images/merch/velvet-avenue-night-shift-poster.svg',19.0,67,'2025-01-17',1);
INSERT INTO "merch_items" VALUES(14,7,14,'Velvet Avenue Setlist Tote','velvet-avenue-setlist-tote','tote','Velvet Avenue Setlist Tote is a tote release tied to Lobby Mirage, printed locally for Velvet Avenue with clean benchmark-ready variant information.','Natural cotton tote printed with a handwritten setlist.','images/merch/velvet-avenue-setlist-tote.svg',24.0,73,'2025-01-22',1);
INSERT INTO "merch_items" VALUES(15,8,15,'Salt Meadow Field Notes Tote','salt-meadow-field-notes-tote','tote','Salt Meadow Field Notes Tote is a tote release tied to Riverlights, printed locally for Salt Meadow with clean benchmark-ready variant information.','Natural tote printed with Riverlights notebook fragments.','images/merch/salt-meadow-field-notes-tote.svg',22.0,69,'2025-06-27',1);
INSERT INTO "merch_items" VALUES(16,8,15,'Salt Meadow Riverlights Lyric Zine','salt-meadow-riverlights-lyric-zine','zine','Salt Meadow Riverlights Lyric Zine is a zine release tied to Riverlights, printed locally for Salt Meadow with clean benchmark-ready variant information.','Staple-bound lyric zine with recording notes and Polaroids.','images/merch/salt-meadow-riverlights-lyric-zine.svg',14.0,75,'2025-07-02',1);
INSERT INTO "merch_items" VALUES(17,9,17,'Iron Veil Chapel Longsleeve','iron-veil-chapel-longsleeve','shirt','Iron Veil Chapel Longsleeve is a shirt release tied to Iron Sleep, printed locally for Iron Veil with clean benchmark-ready variant information.','Longsleeve with metallic ink front and sleeve glyphs.','images/merch/iron-veil-chapel-longsleeve.svg',36.0,71,'2025-11-07',1);
INSERT INTO "merch_items" VALUES(18,9,18,'Iron Veil Noise Patch Set','iron-veil-noise-patch-set','patch','Iron Veil Noise Patch Set is a patch release tied to Saint of Noise, printed locally for Iron Veil with clean benchmark-ready variant information.','Three embroidered patches with silver overlock.','images/merch/iron-veil-noise-patch-set.svg',12.0,77,'2025-11-12',1);
INSERT INTO "merch_items" VALUES(19,10,19,'Fever Arcade Gloss Tee','fever-arcade-gloss-tee','shirt','Fever Arcade Gloss Tee is a shirt release tied to Elastic Hearts, printed locally for Fever Arcade with clean benchmark-ready variant information.','Bright print tee with split-tone Elastic Hearts graphic.','images/merch/fever-arcade-gloss-tee.svg',29.0,73,'2025-11-21',1);
INSERT INTO "merch_items" VALUES(20,10,20,'Fever Arcade Mirror Pin Set','fever-arcade-mirror-pin-set','pin','Fever Arcade Mirror Pin Set is a pin release tied to Mirror Mosaic, printed locally for Fever Arcade with clean benchmark-ready variant information.','Two hard-enamel pins shaped like mirror fragments.','images/merch/fever-arcade-mirror-pin-set.svg',15.0,79,'2025-11-26',1);
INSERT INTO "merch_items" VALUES(21,11,22,'Mono Shrine Fault Choir Zine','mono-shrine-fault-choir-zine','zine','Mono Shrine Fault Choir Zine is a zine release tied to Fault Choir, printed locally for Mono Shrine with clean benchmark-ready variant information.','Eight-page foldout zine of lyric fragments and cassette labels.','images/merch/mono-shrine-fault-choir-zine.svg',13.0,75,'2025-03-14',1);
INSERT INTO "merch_items" VALUES(22,11,21,'Mono Shrine Resin Poster','mono-shrine-resin-poster','poster','Mono Shrine Resin Poster is a poster release tied to Resin Language, printed locally for Mono Shrine with clean benchmark-ready variant information.','A2 poster using the album''s resin-grid art.','images/merch/mono-shrine-resin-poster.svg',17.0,81,'2025-03-19',0);
INSERT INTO "merch_items" VALUES(23,12,23,'Tide Static Burn Tee','tide-static-burn-tee','shirt','Tide Static Burn Tee is a shirt release tied to Harbor Burn, printed locally for Tide Static with clean benchmark-ready variant information.','Vintage white tee with a cracked orange harbor-burn print.','images/merch/tide-static-burn-tee.svg',30.0,77,'2025-06-13',1);
INSERT INTO "merch_items" VALUES(24,12,24,'Tide Static Quiet Engine Tote','tide-static-quiet-engine-tote','tote','Tide Static Quiet Engine Tote is a tote release tied to Quiet Engine, printed locally for Tide Static with clean benchmark-ready variant information.','Canvas tote featuring the Quiet Engine highway diagram.','images/merch/tide-static-quiet-engine-tote.svg',21.0,83,'2025-06-18',0);
INSERT INTO "merch_items" VALUES(25,13,25,'Amber Relay Tour Tee','amber-relay-tour-tee','shirt','Amber Relay Tour Tee is a shirt release tied to Static Weather, printed locally for Amber Relay with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/amber-relay-tour-tee.svg',29.0,79,'2024-04-17',1);
INSERT INTO "merch_items" VALUES(26,13,26,'Amber Relay Carry Tote','amber-relay-carry-tote','tote','Amber Relay Carry Tote is a tote release tied to Quiet Vector, printed locally for Amber Relay with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/amber-relay-carry-tote.svg',21.0,85,'2024-04-22',0);
INSERT INTO "merch_items" VALUES(27,14,27,'Paper Current Tour Tee','paper-current-tour-tee','shirt','Paper Current Tour Tee is a shirt release tied to Harbor Ledger, printed locally for Paper Current with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/paper-current-tour-tee.svg',30.0,81,'2025-05-23',1);
INSERT INTO "merch_items" VALUES(28,14,28,'Paper Current Carry Tote','paper-current-carry-tote','tote','Paper Current Carry Tote is a tote release tied to Paper Thread, printed locally for Paper Current with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/paper-current-carry-tote.svg',22.0,87,'2025-05-28',0);
INSERT INTO "merch_items" VALUES(29,15,29,'Silver Weather Tour Tee','silver-weather-tour-tee','shirt','Silver Weather Tour Tee is a shirt release tied to River Cinema, printed locally for Silver Weather with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/silver-weather-tour-tee.svg',31.0,83,'2026-06-27',1);
INSERT INTO "merch_items" VALUES(30,15,30,'Silver Weather Carry Tote','silver-weather-carry-tote','tote','Silver Weather Carry Tote is a tote release tied to Chrome Parade, printed locally for Silver Weather with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/silver-weather-carry-tote.svg',23.0,89,'2026-07-02',0);
INSERT INTO "merch_items" VALUES(31,16,31,'North Routine Tour Tee','north-routine-tour-tee','shirt','North Routine Tour Tee is a shirt release tied to Signal Method, printed locally for North Routine with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/north-routine-tour-tee.svg',32.0,85,'2026-03-27',1);
INSERT INTO "merch_items" VALUES(32,16,32,'North Routine Carry Tote','north-routine-carry-tote','tote','North Routine Carry Tote is a tote release tied to South Engine, printed locally for North Routine with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/north-routine-carry-tote.svg',21.0,91,'2026-04-01',0);
INSERT INTO "merch_items" VALUES(33,17,33,'Copper Bloom Tour Tee','copper-bloom-tour-tee','shirt','Copper Bloom Tour Tee is a shirt release tied to Blue Current, printed locally for Copper Bloom with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/copper-bloom-tour-tee.svg',29.0,87,'2025-09-07',1);
INSERT INTO "merch_items" VALUES(34,17,34,'Copper Bloom Carry Tote','copper-bloom-carry-tote','tote','Copper Bloom Carry Tote is a tote release tied to Midnight Signal, printed locally for Copper Bloom with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/copper-bloom-carry-tote.svg',22.0,93,'2025-09-12',0);
INSERT INTO "merch_items" VALUES(35,18,35,'Ladder Choir Tour Tee','ladder-choir-tour-tee','shirt','Ladder Choir Tour Tee is a shirt release tied to Late Boulevard, printed locally for Ladder Choir with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/ladder-choir-tour-tee.svg',30.0,89,'2026-09-18',1);
INSERT INTO "merch_items" VALUES(36,18,36,'Ladder Choir Carry Tote','ladder-choir-carry-tote','tote','Ladder Choir Carry Tote is a tote release tied to Glass Mosaic, printed locally for Ladder Choir with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/ladder-choir-carry-tote.svg',23.0,95,'2026-09-23',0);
INSERT INTO "merch_items" VALUES(37,19,37,'Hour Motel Tour Tee','hour-motel-tour-tee','shirt','Hour Motel Tour Tee is a shirt release tied to Golden Garden, printed locally for Hour Motel with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/hour-motel-tour-tee.svg',31.0,91,'2025-07-05',1);
INSERT INTO "merch_items" VALUES(38,19,38,'Hour Motel Carry Tote','hour-motel-carry-tote','tote','Hour Motel Carry Tote is a tote release tied to Motel Harbor, printed locally for Hour Motel with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/hour-motel-carry-tote.svg',21.0,97,'2025-07-10',0);
INSERT INTO "merch_items" VALUES(39,20,39,'Signal Lake Tour Tee','signal-lake-tour-tee','shirt','Signal Lake Tour Tee is a shirt release tied to Quiet Transit, printed locally for Signal Lake with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/signal-lake-tour-tee.svg',32.0,93,'2026-08-08',1);
INSERT INTO "merch_items" VALUES(40,20,40,'Signal Lake Carry Tote','signal-lake-carry-tote','tote','Signal Lake Carry Tote is a tote release tied to Stone Circuit, printed locally for Signal Lake with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/signal-lake-carry-tote.svg',22.0,99,'2026-08-13',0);
INSERT INTO "merch_items" VALUES(41,21,41,'Delta Hall Tour Tee','delta-hall-tour-tee','shirt','Delta Hall Tour Tee is a shirt release tied to Paper Archive, printed locally for Delta Hall with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/delta-hall-tour-tee.svg',29.0,95,'2026-02-03',1);
INSERT INTO "merch_items" VALUES(42,21,42,'Delta Hall Carry Tote','delta-hall-carry-tote','tote','Delta Hall Carry Tote is a tote release tied to Delta Minutes, printed locally for Delta Hall with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/delta-hall-carry-tote.svg',23.0,101,'2026-02-08',0);
INSERT INTO "merch_items" VALUES(43,22,43,'Mirror Union Tour Tee','mirror-union-tour-tee','shirt','Mirror Union Tour Tee is a shirt release tied to Chrome Pattern, printed locally for Mirror Union with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/mirror-union-tour-tee.svg',30.0,97,'2024-09-20',1);
INSERT INTO "merch_items" VALUES(44,22,44,'Mirror Union Carry Tote','mirror-union-carry-tote','tote','Mirror Union Carry Tote is a tote release tied to Velvet Weather, printed locally for Mirror Union with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/mirror-union-carry-tote.svg',21.0,103,'2024-09-25',0);
INSERT INTO "merch_items" VALUES(45,23,45,'Quiet Metric Tour Tee','quiet-metric-tour-tee','shirt','Quiet Metric Tour Tee is a shirt release tied to South Dusk, printed locally for Quiet Metric with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/quiet-metric-tour-tee.svg',31.0,99,'2025-10-24',1);
INSERT INTO "merch_items" VALUES(46,23,46,'Quiet Metric Carry Tote','quiet-metric-carry-tote','tote','Quiet Metric Carry Tote is a tote release tied to Open Ledger, printed locally for Quiet Metric with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/quiet-metric-carry-tote.svg',22.0,105,'2025-10-29',0);
INSERT INTO "merch_items" VALUES(47,24,47,'Blue Archive Tour Tee','blue-archive-tour-tee','shirt','Blue Archive Tour Tee is a shirt release tied to Midnight Vector, printed locally for Blue Archive with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/blue-archive-tour-tee.svg',32.0,101,'2026-04-24',1);
INSERT INTO "merch_items" VALUES(48,24,48,'Blue Archive Carry Tote','blue-archive-carry-tote','tote','Blue Archive Carry Tote is a tote release tied to After Cinema, printed locally for Blue Archive with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/blue-archive-carry-tote.svg',23.0,107,'2026-04-29',0);
INSERT INTO "merch_items" VALUES(49,25,49,'Stair Pattern Tour Tee','stair-pattern-tour-tee','shirt','Stair Pattern Tour Tee is a shirt release tied to Glass Thread, printed locally for Stair Pattern with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/stair-pattern-tour-tee.svg',29.0,103,'2024-05-30',1);
INSERT INTO "merch_items" VALUES(50,25,50,'Stair Pattern Carry Tote','stair-pattern-carry-tote','tote','Stair Pattern Carry Tote is a tote release tied to Broken Method, printed locally for Stair Pattern with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/stair-pattern-carry-tote.svg',21.0,109,'2024-06-04',0);
INSERT INTO "merch_items" VALUES(51,26,51,'Velvet Current Tour Tee','velvet-current-tour-tee','shirt','Velvet Current Tour Tee is a shirt release tied to Motel Parade, printed locally for Velvet Current with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/velvet-current-tour-tee.svg',30.0,105,'2025-07-04',1);
INSERT INTO "merch_items" VALUES(52,26,52,'Velvet Current Carry Tote','velvet-current-carry-tote','tote','Velvet Current Carry Tote is a tote release tied to Static Current, printed locally for Velvet Current with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/velvet-current-carry-tote.svg',22.0,111,'2025-07-09',0);
INSERT INTO "merch_items" VALUES(53,27,53,'Harbor Study Tour Tee','harbor-study-tour-tee','shirt','Harbor Study Tour Tee is a shirt release tied to Stone Engine, printed locally for Harbor Study with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/harbor-study-tour-tee.svg',31.0,107,'2026-08-09',1);
INSERT INTO "merch_items" VALUES(54,27,54,'Harbor Study Carry Tote','harbor-study-carry-tote','tote','Harbor Study Carry Tote is a tote release tied to Harbor Boulevard, printed locally for Harbor Study with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/harbor-study-carry-tote.svg',23.0,113,'2026-08-14',0);
INSERT INTO "merch_items" VALUES(55,28,55,'Street Lantern Tour Tee','street-lantern-tour-tee','shirt','Street Lantern Tour Tee is a shirt release tied to Delta Signal, printed locally for Street Lantern with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/street-lantern-tour-tee.svg',32.0,109,'2026-05-08',1);
INSERT INTO "merch_items" VALUES(56,28,56,'Street Lantern Carry Tote','street-lantern-carry-tote','tote','Street Lantern Carry Tote is a tote release tied to River Garden, printed locally for Street Lantern with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/street-lantern-carry-tote.svg',21.0,115,'2026-05-13',0);
INSERT INTO "merch_items" VALUES(57,29,57,'Noon Frame Tour Tee','noon-frame-tour-tee','shirt','Noon Frame Tour Tee is a shirt release tied to Velvet Mosaic, printed locally for Noon Frame with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/noon-frame-tour-tee.svg',29.0,111,'2025-09-25',1);
INSERT INTO "merch_items" VALUES(58,29,58,'Noon Frame Carry Tote','noon-frame-carry-tote','tote','Noon Frame Carry Tote is a tote release tied to Signal Transit, printed locally for Noon Frame with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/noon-frame-carry-tote.svg',22.0,117,'2025-09-30',0);
INSERT INTO "merch_items" VALUES(59,30,59,'Low Atlas Tour Tee','low-atlas-tour-tee','shirt','Low Atlas Tour Tee is a shirt release tied to Open Harbor, printed locally for Low Atlas with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/low-atlas-tour-tee.svg',30.0,113,'2026-10-31',1);
INSERT INTO "merch_items" VALUES(60,30,60,'Low Atlas Carry Tote','low-atlas-carry-tote','tote','Low Atlas Carry Tote is a tote release tied to Blue Archive, printed locally for Low Atlas with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/low-atlas-carry-tote.svg',23.0,119,'2026-11-05',0);
INSERT INTO "merch_items" VALUES(61,31,61,'Chrome Willow Tour Tee','chrome-willow-tour-tee','shirt','Chrome Willow Tour Tee is a shirt release tied to After Circuit, printed locally for Chrome Willow with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/chrome-willow-tour-tee.svg',31.0,115,'2025-07-24',1);
INSERT INTO "merch_items" VALUES(62,31,62,'Chrome Willow Carry Tote','chrome-willow-carry-tote','tote','Chrome Willow Carry Tote is a tote release tied to Late Pattern, printed locally for Chrome Willow with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/chrome-willow-carry-tote.svg',21.0,121,'2025-07-29',0);
INSERT INTO "merch_items" VALUES(63,32,63,'Radio Meadow Tour Tee','radio-meadow-tour-tee','shirt','Radio Meadow Tour Tee is a shirt release tied to Broken Minutes, printed locally for Radio Meadow with clean benchmark-ready variant information.','Standard artist tee with benchmark-ready sizing.','images/merch/radio-meadow-tour-tee.svg',32.0,117,'2026-08-27',1);
INSERT INTO "merch_items" VALUES(64,32,64,'Radio Meadow Carry Tote','radio-meadow-carry-tote','tote','Radio Meadow Carry Tote is a tote release tied to Golden Dusk, printed locally for Radio Meadow with clean benchmark-ready variant information.','Canvas tote with scene-specific line work.','images/merch/radio-meadow-carry-tote.svg',22.0,123,'2026-09-01',0);
INSERT INTO "merch_items" VALUES(65,33,NULL,'Fault Parade Tour Tee','fault-parade-tour-tee','shirt','Fault Parade Tour Tee is a shirt item from Fault Parade, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/fault-parade-tour-tee.svg',29.0,119,'2026-02-19',1);
INSERT INTO "merch_items" VALUES(66,33,NULL,'Fault Parade Carry Tote','fault-parade-carry-tote','tote','Fault Parade Carry Tote is a tote item from Fault Parade, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/fault-parade-carry-tote.svg',23.0,125,'2026-02-24',0);
INSERT INTO "merch_items" VALUES(67,34,NULL,'Static Ledger Tour Tee','static-ledger-tour-tee','shirt','Static Ledger Tour Tee is a shirt item from Static Ledger, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/static-ledger-tour-tee.svg',30.0,121,'2024-11-02',1);
INSERT INTO "merch_items" VALUES(68,34,NULL,'Static Ledger Carry Tote','static-ledger-carry-tote','tote','Static Ledger Carry Tote is a tote item from Static Ledger, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/static-ledger-carry-tote.svg',21.0,127,'2024-11-07',0);
INSERT INTO "merch_items" VALUES(69,35,NULL,'Stone Balcony Tour Tee','stone-balcony-tour-tee','shirt','Stone Balcony Tour Tee is a shirt item from Stone Balcony, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/stone-balcony-tour-tee.svg',31.0,123,'2025-05-01',1);
INSERT INTO "merch_items" VALUES(70,35,NULL,'Stone Balcony Carry Tote','stone-balcony-carry-tote','tote','Stone Balcony Carry Tote is a tote item from Stone Balcony, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/stone-balcony-carry-tote.svg',22.0,129,'2025-05-06',0);
INSERT INTO "merch_items" VALUES(71,36,NULL,'West Transit Tour Tee','west-transit-tour-tee','shirt','West Transit Tour Tee is a shirt item from West Transit, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/west-transit-tour-tee.svg',32.0,125,'2026-06-06',1);
INSERT INTO "merch_items" VALUES(72,36,NULL,'West Transit Carry Tote','west-transit-carry-tote','tote','West Transit Carry Tote is a tote item from West Transit, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/west-transit-carry-tote.svg',23.0,131,'2026-06-11',0);
INSERT INTO "merch_items" VALUES(73,37,NULL,'Echo Dividend Tour Tee','echo-dividend-tour-tee','shirt','Echo Dividend Tour Tee is a shirt item from Echo Dividend, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/echo-dividend-tour-tee.svg',29.0,127,'2024-06-17',1);
INSERT INTO "merch_items" VALUES(74,37,NULL,'Echo Dividend Carry Tote','echo-dividend-carry-tote','tote','Echo Dividend Carry Tote is a tote item from Echo Dividend, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/echo-dividend-carry-tote.svg',21.0,133,'2024-06-22',0);
INSERT INTO "merch_items" VALUES(75,38,NULL,'Cloud Bureau Tour Tee','cloud-bureau-tour-tee','shirt','Cloud Bureau Tour Tee is a shirt item from Cloud Bureau, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/cloud-bureau-tour-tee.svg',30.0,129,'2025-07-23',1);
INSERT INTO "merch_items" VALUES(76,38,NULL,'Cloud Bureau Carry Tote','cloud-bureau-carry-tote','tote','Cloud Bureau Carry Tote is a tote item from Cloud Bureau, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/cloud-bureau-carry-tote.svg',22.0,135,'2025-07-28',0);
INSERT INTO "merch_items" VALUES(77,39,NULL,'Ridge Cinema Tour Tee','ridge-cinema-tour-tee','shirt','Ridge Cinema Tour Tee is a shirt item from Ridge Cinema, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/ridge-cinema-tour-tee.svg',31.0,131,'2026-08-28',1);
INSERT INTO "merch_items" VALUES(78,39,NULL,'Ridge Cinema Carry Tote','ridge-cinema-carry-tote','tote','Ridge Cinema Carry Tote is a tote item from Ridge Cinema, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/ridge-cinema-carry-tote.svg',23.0,137,'2026-09-02',0);
INSERT INTO "merch_items" VALUES(79,40,NULL,'Hollow Method Tour Tee','hollow-method-tour-tee','shirt','Hollow Method Tour Tee is a shirt item from Hollow Method, created for the local mirror with deterministic colors and edition notes.','Standard artist tee with benchmark-ready sizing.','images/merch/hollow-method-tour-tee.svg',32.0,133,'2026-05-27',1);
INSERT INTO "merch_items" VALUES(80,40,NULL,'Hollow Method Carry Tote','hollow-method-carry-tote','tote','Hollow Method Carry Tote is a tote item from Hollow Method, created for the local mirror with deterministic colors and edition notes.','Canvas tote with scene-specific line work.','images/merch/hollow-method-carry-tote.svg',21.0,139,'2026-06-01',0);
CREATE TABLE order_items (
	id INTEGER NOT NULL, 
	order_id INTEGER NOT NULL, 
	album_id INTEGER, 
	merch_item_id INTEGER, 
	format_variant_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	artist_name VARCHAR(140), 
	image_path VARCHAR(255), 
	variant_label VARCHAR(160), 
	quantity INTEGER, 
	unit_price FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(merch_item_id) REFERENCES merch_items (id), 
	FOREIGN KEY(format_variant_id) REFERENCES format_variants (id)
);
INSERT INTO "order_items" VALUES(1,1,13,NULL,64,'Blue Hour Broadcast','Velvet Avenue','images/covers/blue-hour-broadcast.svg','Colored Vinyl · 12-inch · Ocean Blue',1,25.0);
INSERT INTO "order_items" VALUES(2,1,NULL,13,70,'Velvet Avenue Night Shift Poster','Velvet Avenue','images/merch/velvet-avenue-night-shift-poster.svg','Signed · 18x24',1,27.0);
INSERT INTO "order_items" VALUES(3,2,1,NULL,1,'Tidal Memory','Neon Harbor','images/covers/tidal-memory.svg','Digital Album · MP3 + FLAC',1,8.5);
INSERT INTO "order_items" VALUES(4,3,11,NULL,55,'Signal Debt','Cinder Plaza','images/covers/signal-debt.svg','Digital Album · MP3 + FLAC',1,8.5);
INSERT INTO "order_items" VALUES(5,3,21,NULL,108,'Resin Language','Mono Shrine','images/covers/resin-language.svg','Cassette · Transparent Shell',1,15.0);
INSERT INTO "order_items" VALUES(6,4,7,NULL,35,'Between Stations','Soft Locale','images/covers/between-stations.svg','Cassette · Transparent Shell',1,14.5);
INSERT INTO "order_items" VALUES(7,4,NULL,7,40,'Soft Locale Drift Hoodie','Soft Locale','images/merch/soft-locale-drift-hoodie.svg','Drift Hoodie · M · Stone',1,48.0);
INSERT INTO "order_items" VALUES(8,5,19,NULL,97,'Elastic Hearts','Fever Arcade','images/covers/elastic-hearts.svg','Compact Disc · Gatefold',1,17.0);
INSERT INTO "order_items" VALUES(9,5,NULL,15,79,'Salt Meadow Field Notes Tote','Salt Meadow','images/merch/salt-meadow-field-notes-tote.svg','Field Notes Tote · Natural',1,22.0);
CREATE TABLE orders (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	order_number VARCHAR(60) NOT NULL, 
	status VARCHAR(40), 
	subtotal FLOAT, 
	shipping FLOAT, 
	tax FLOAT, 
	total FLOAT, 
	shipping_name VARCHAR(140), 
	shipping_line1 VARCHAR(200), 
	shipping_city VARCHAR(120), 
	shipping_country VARCHAR(120), 
	payment_label VARCHAR(120), 
	note VARCHAR(240), 
	placed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (order_number)
);
INSERT INTO "orders" VALUES(1,1,'BC-20260414-0001','delivered',52.0,0.0,4.29,56.29,'Alice Johnson','128 Lake Union Ave','Seattle','United States','Visa ending in 4242','Deterministic benchmark seed order.','2026-04-14 12:00:00.000000');
INSERT INTO "orders" VALUES(2,1,'BC-20260426-0002','processing',8.5,6.5,0.7,15.7,'Alice Johnson','128 Lake Union Ave','Seattle','United States','Visa ending in 1177','Deterministic benchmark seed order.','2026-04-26 12:00:00.000000');
INSERT INTO "orders" VALUES(3,2,'BC-20260409-0003','delivered',23.5,6.5,1.94,31.94,'Bob Chen','77 Fulton Market','Chicago','United States','Mastercard ending in 7788','Deterministic benchmark seed order.','2026-04-09 12:00:00.000000');
INSERT INTO "orders" VALUES(4,3,'BC-20260421-0004','delivered',62.5,0.0,5.16,67.66,'Carol Davis','55 Bergen St','Brooklyn','United States','Visa ending in 9901','Deterministic benchmark seed order.','2026-04-21 12:00:00.000000');
INSERT INTO "orders" VALUES(5,4,'BC-20260428-0005','shipped',39.0,6.5,3.22,48.72,'David Kim','204 Burnside St','Portland','United States','Amex ending in 3401','Deterministic benchmark seed order.','2026-04-28 12:00:00.000000');
CREATE TABLE scenes (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	country VARCHAR(80), 
	description TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
INSERT INTO "scenes" VALUES(1,'Los Angeles, United States','los-angeles-united-states','United States','Sun-bleached studios, late-night FM nostalgia, and movie-score sheen.');
INSERT INTO "scenes" VALUES(2,'Berlin, Germany','berlin-germany','Germany','Dub chambers, warehouse drums, and experimental club cross-pollination.');
INSERT INTO "scenes" VALUES(3,'Tokyo, Japan','tokyo-japan','Japan','Compact detail, commuter ambience, and hyper-precise sound design.');
INSERT INTO "scenes" VALUES(4,'London, United Kingdom','london-united-kingdom','United Kingdom','Independent label culture with left turns into post-punk, jazz, and pop.');
INSERT INTO "scenes" VALUES(5,'New York, United States','new-york-united-states','United States','Small-room virtuosity, art-school hooks, and downtown improvisation.');
INSERT INTO "scenes" VALUES(6,'Melbourne, Australia','melbourne-australia','Australia','Open-hearted songwriting, DIY scenes, and tactile physical editions.');
INSERT INTO "scenes" VALUES(7,'Sao Paulo, Brazil','sao-paulo-brazil','Brazil','Percussive movement, raw punk energy, and bright visual identity.');
INSERT INTO "scenes" VALUES(8,'Detroit, United States','detroit-united-states','United States','Machine rhythm, soul memory, and durable underground infrastructure.');
INSERT INTO "scenes" VALUES(9,'Paris, France','paris-france','France','Elegant arrangements, metallic tension, and art-book presentation.');
CREATE TABLE tags (
	id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
INSERT INTO "tags" VALUES(1,'dub techno','dub-techno');
INSERT INTO "tags" VALUES(2,'afterhours','afterhours');
INSERT INTO "tags" VALUES(3,'submerged','submerged');
INSERT INTO "tags" VALUES(4,'Berlin','berlin');
INSERT INTO "tags" VALUES(5,'deep groove','deep-groove');
INSERT INTO "tags" VALUES(6,'modular','modular');
INSERT INTO "tags" VALUES(7,'late deck','late-deck');
INSERT INTO "tags" VALUES(8,'dream pop','dream-pop');
INSERT INTO "tags" VALUES(9,'reverb','reverb');
INSERT INTO "tags" VALUES(10,'overcast hooks','overcast-hooks');
INSERT INTO "tags" VALUES(11,'London','london');
INSERT INTO "tags" VALUES(12,'shoegaze','shoegaze');
INSERT INTO "tags" VALUES(13,'jangle','jangle');
INSERT INTO "tags" VALUES(14,'bedroom','bedroom');
INSERT INTO "tags" VALUES(15,'warehouse','warehouse');
INSERT INTO "tags" VALUES(16,'analog','analog');
INSERT INTO "tags" VALUES(17,'strobe','strobe');
INSERT INTO "tags" VALUES(18,'Detroit','detroit');
INSERT INTO "tags" VALUES(19,'acid','acid');
INSERT INTO "tags" VALUES(20,'tool track','tool-track');
INSERT INTO "tags" VALUES(21,'ferrous','ferrous');
INSERT INTO "tags" VALUES(22,'commuter','commuter');
INSERT INTO "tags" VALUES(23,'late train','late-train');
INSERT INTO "tags" VALUES(24,'sleep tape','sleep-tape');
INSERT INTO "tags" VALUES(25,'Tokyo','tokyo');
INSERT INTO "tags" VALUES(26,'drone','drone');
INSERT INTO "tags" VALUES(27,'meditation','meditation');
INSERT INTO "tags" VALUES(28,'field recordings','field-recordings');
INSERT INTO "tags" VALUES(29,'d-beat','d-beat');
INSERT INTO "tags" VALUES(30,'DIY','diy');
INSERT INTO "tags" VALUES(31,'street flyer','street-flyer');
INSERT INTO "tags" VALUES(32,'Sao Paulo','sao-paulo');
INSERT INTO "tags" VALUES(33,'basement','basement');
INSERT INTO "tags" VALUES(34,'agitprop','agitprop');
INSERT INTO "tags" VALUES(35,'sprint','sprint');
INSERT INTO "tags" VALUES(36,'lyric sheet','lyric-sheet');
INSERT INTO "tags" VALUES(37,'left field','left-field');
INSERT INTO "tags" VALUES(38,'city pressure','city-pressure');
INSERT INTO "tags" VALUES(39,'Los Angeles','los-angeles');
INSERT INTO "tags" VALUES(40,'jazz rap','jazz-rap');
INSERT INTO "tags" VALUES(41,'loop heavy','loop-heavy');
INSERT INTO "tags" VALUES(42,'basement tape','basement-tape');
INSERT INTO "tags" VALUES(43,'late set','late-set');
INSERT INTO "tags" VALUES(44,'trio','trio');
INSERT INTO "tags" VALUES(45,'blue room','blue-room');
INSERT INTO "tags" VALUES(46,'New York','new-york');
INSERT INTO "tags" VALUES(47,'modal','modal');
INSERT INTO "tags" VALUES(48,'horn blend','horn-blend');
INSERT INTO "tags" VALUES(49,'improv','improv');
INSERT INTO "tags" VALUES(50,'story song','story-song');
INSERT INTO "tags" VALUES(51,'field note','field-note');
INSERT INTO "tags" VALUES(52,'river road','river-road');
INSERT INTO "tags" VALUES(53,'Melbourne','melbourne');
INSERT INTO "tags" VALUES(54,'americana','americana');
INSERT INTO "tags" VALUES(55,'soft harmonies','soft-harmonies');
INSERT INTO "tags" VALUES(56,'slow weather','slow-weather');
INSERT INTO "tags" VALUES(57,'doom','doom');
INSERT INTO "tags" VALUES(58,'ritual','ritual');
INSERT INTO "tags" VALUES(59,'cathedral reverb','cathedral-reverb');
INSERT INTO "tags" VALUES(60,'Paris','paris');
INSERT INTO "tags" VALUES(61,'blackened','blackened');
INSERT INTO "tags" VALUES(62,'ash cloud','ash-cloud');
INSERT INTO "tags" VALUES(63,'blast beat','blast-beat');
INSERT INTO "tags" VALUES(64,'hook','hook');
INSERT INTO "tags" VALUES(65,'night drive','night-drive');
INSERT INTO "tags" VALUES(66,'bright chorus','bright-chorus');
INSERT INTO "tags" VALUES(67,'synth pop','synth-pop');
INSERT INTO "tags" VALUES(68,'gloss','gloss');
INSERT INTO "tags" VALUES(69,'dancefloor','dancefloor');
INSERT INTO "tags" VALUES(70,'collage','collage');
INSERT INTO "tags" VALUES(71,'tape hiss','tape-hiss');
INSERT INTO "tags" VALUES(72,'microtone','microtone');
INSERT INTO "tags" VALUES(73,'glitch','glitch');
INSERT INTO "tags" VALUES(74,'avant pop','avant-pop');
INSERT INTO "tags" VALUES(75,'noise drift','noise-drift');
INSERT INTO "tags" VALUES(76,'psych rock','psych-rock');
INSERT INTO "tags" VALUES(77,'motorik','motorik');
INSERT INTO "tags" VALUES(78,'widescreen','widescreen');
INSERT INTO "tags" VALUES(79,'garage','garage');
INSERT INTO "tags" VALUES(80,'riff driven','riff-driven');
INSERT INTO "tags" VALUES(81,'festival ready','festival-ready');
INSERT INTO "tags" VALUES(82,'drum machine','drum-machine');
INSERT INTO "tags" VALUES(83,'indie rock','indie-rock');
INSERT INTO "tags" VALUES(84,'burnt amp','burnt-amp');
INSERT INTO "tags" VALUES(85,'soundscape','soundscape');
INSERT INTO "tags" VALUES(86,'boom bap','boom-bap');
INSERT INTO "tags" VALUES(87,'spiritual','spiritual');
INSERT INTO "tags" VALUES(88,'acoustic','acoustic');
INSERT INTO "tags" VALUES(89,'heartbreak','heartbreak');
INSERT INTO "tags" VALUES(90,'four on the floor','four-on-the-floor');
CREATE TABLE tracks (
	id INTEGER NOT NULL, 
	album_id INTEGER NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	slug VARCHAR(180) NOT NULL, 
	track_number INTEGER NOT NULL, 
	duration_seconds INTEGER, 
	preview_hook VARCHAR(255), 
	lyrics_excerpt TEXT, 
	is_focus_track BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id)
);
INSERT INTO "tracks" VALUES(1,1,'Incoming Tide','tidal-memory-incoming-tide',1,184,'Incoming Tide is the preview focus from Tidal Memory.','Incoming Tide traces the emotional contour of tidal memory in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(2,1,'Mooring Light','tidal-memory-mooring-light',2,213,'Mooring Light is the preview focus from Tidal Memory.','Mooring Light traces the emotional contour of tidal memory in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(3,1,'Breakwater','tidal-memory-breakwater',3,242,'Breakwater is the preview focus from Tidal Memory.','Breakwater traces the emotional contour of tidal memory in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(4,1,'Low Pier','tidal-memory-low-pier',4,271,'Low Pier is the preview focus from Tidal Memory.','Low Pier traces the emotional contour of tidal memory in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(5,1,'Morning Channel','tidal-memory-morning-channel',5,300,'Morning Channel is the preview focus from Tidal Memory.','Morning Channel traces the emotional contour of tidal memory in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(6,2,'Platform Sleep','night-ferry-platform-sleep',1,205,'Platform Sleep is the preview focus from Night Ferry.','Platform Sleep traces the emotional contour of night ferry in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(7,2,'Signal Two','night-ferry-signal-two',2,234,'Signal Two is the preview focus from Night Ferry.','Signal Two traces the emotional contour of night ferry in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(8,2,'Dock Exchange','night-ferry-dock-exchange',3,263,'Dock Exchange is the preview focus from Night Ferry.','Dock Exchange traces the emotional contour of night ferry in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(9,2,'Wake Window','night-ferry-wake-window',4,292,'Wake Window is the preview focus from Night Ferry.','Wake Window traces the emotional contour of night ferry in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(10,2,'Westbound Static','night-ferry-westbound-static',5,321,'Westbound Static is the preview focus from Night Ferry.','Westbound Static traces the emotional contour of night ferry in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(11,3,'Glasshouse Lobby','static-bloom-glasshouse-lobby',1,197,'Glasshouse Lobby is the preview focus from Static Bloom.','Glasshouse Lobby traces the emotional contour of static bloom in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(12,3,'Northbound Blue','static-bloom-northbound-blue',2,226,'Northbound Blue is the preview focus from Static Bloom.','Northbound Blue traces the emotional contour of static bloom in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(13,3,'Tin Roof Weather','static-bloom-tin-roof-weather',3,255,'Tin Roof Weather is the preview focus from Static Bloom.','Tin Roof Weather traces the emotional contour of static bloom in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(14,3,'Run the Balcony','static-bloom-run-the-balcony',4,284,'Run the Balcony is the preview focus from Static Bloom.','Run the Balcony traces the emotional contour of static bloom in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(15,3,'Static Bloom','static-bloom-static-bloom',5,313,'Static Bloom is the preview focus from Static Bloom.','Static Bloom traces the emotional contour of static bloom in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(16,4,'Sunday Turnstile','paper-signal-sunday-turnstile',1,218,'Sunday Turnstile is the preview focus from Paper Signal.','Sunday Turnstile traces the emotional contour of paper signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(17,4,'Fluorescent Map','paper-signal-fluorescent-map',2,247,'Fluorescent Map is the preview focus from Paper Signal.','Fluorescent Map traces the emotional contour of paper signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(18,4,'Paper Signal','paper-signal-paper-signal',3,276,'Paper Signal is the preview focus from Paper Signal.','Paper Signal traces the emotional contour of paper signal in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(19,4,'Taxi Dust','paper-signal-taxi-dust',4,305,'Taxi Dust is the preview focus from Paper Signal.','Taxi Dust traces the emotional contour of paper signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(20,4,'Window Figures','paper-signal-window-figures',5,164,'Window Figures is the preview focus from Paper Signal.','Window Figures traces the emotional contour of paper signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(21,5,'Factory Dawn','redline-ritual-factory-dawn',1,210,'Factory Dawn is the preview focus from Redline Ritual.','Factory Dawn traces the emotional contour of redline ritual in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(22,5,'Heater Coil','redline-ritual-heater-coil',2,239,'Heater Coil is the preview focus from Redline Ritual.','Heater Coil traces the emotional contour of redline ritual in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(23,5,'Redline Ritual','redline-ritual-redline-ritual',3,268,'Redline Ritual is the preview focus from Redline Ritual.','Redline Ritual traces the emotional contour of redline ritual in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(24,5,'Locked Loop','redline-ritual-locked-loop',4,297,'Locked Loop is the preview focus from Redline Ritual.','Locked Loop traces the emotional contour of redline ritual in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(25,5,'Night Shift Press','redline-ritual-night-shift-press',5,156,'Night Shift Press is the preview focus from Redline Ritual.','Night Shift Press traces the emotional contour of redline ritual in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(26,6,'Servo Chant','machine-prayer-servo-chant',1,231,'Servo Chant is the preview focus from Machine Prayer.','Servo Chant traces the emotional contour of machine prayer in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(27,6,'Welded Saints','machine-prayer-welded-saints',2,260,'Welded Saints is the preview focus from Machine Prayer.','Welded Saints traces the emotional contour of machine prayer in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(28,6,'Machine Prayer','machine-prayer-machine-prayer',3,289,'Machine Prayer is the preview focus from Machine Prayer.','Machine Prayer traces the emotional contour of machine prayer in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(29,6,'Bulkhead Glow','machine-prayer-bulkhead-glow',4,318,'Bulkhead Glow is the preview focus from Machine Prayer.','Bulkhead Glow traces the emotional contour of machine prayer in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(30,6,'After Conveyor','machine-prayer-after-conveyor',5,177,'After Conveyor is the preview focus from Machine Prayer.','After Conveyor traces the emotional contour of machine prayer in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(31,7,'Transfer Bell','between-stations-transfer-bell',1,223,'Transfer Bell is the preview focus from Between Stations.','Transfer Bell traces the emotional contour of between stations in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(32,7,'Quiet Platform','between-stations-quiet-platform',2,252,'Quiet Platform is the preview focus from Between Stations.','Quiet Platform traces the emotional contour of between stations in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(33,7,'Between Stations','between-stations-between-stations',3,281,'Between Stations is the preview focus from Between Stations.','Between Stations traces the emotional contour of between stations in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(34,7,'River Line','between-stations-river-line',4,310,'River Line is the preview focus from Between Stations.','River Line traces the emotional contour of between stations in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(35,7,'Window Heat','between-stations-window-heat',5,169,'Window Heat is the preview focus from Between Stations.','Window Heat traces the emotional contour of between stations in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(36,8,'Pocket Lantern','sleep-maps-pocket-lantern',1,244,'Pocket Lantern is the preview focus from Sleep Maps.','Pocket Lantern traces the emotional contour of sleep maps in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(37,8,'Hallway Air','sleep-maps-hallway-air',2,273,'Hallway Air is the preview focus from Sleep Maps.','Hallway Air traces the emotional contour of sleep maps in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(38,8,'Sleep Maps','sleep-maps-sleep-maps',3,302,'Sleep Maps is the preview focus from Sleep Maps.','Sleep Maps traces the emotional contour of sleep maps in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(39,8,'Paper Screen','sleep-maps-paper-screen',4,161,'Paper Screen is the preview focus from Sleep Maps.','Paper Screen traces the emotional contour of sleep maps in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(40,8,'End of Service','sleep-maps-end-of-service',5,190,'End of Service is the preview focus from Sleep Maps.','End of Service traces the emotional contour of sleep maps in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(41,9,'Bus Lane','concrete-carnival-bus-lane',1,236,'Bus Lane is the preview focus from Concrete Carnival.','Bus Lane traces the emotional contour of concrete carnival in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(42,9,'Concrete Carnival','concrete-carnival-concrete-carnival',2,265,'Concrete Carnival is the preview focus from Concrete Carnival.','Concrete Carnival traces the emotional contour of concrete carnival in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(43,9,'Sticker Wall','concrete-carnival-sticker-wall',3,294,'Sticker Wall is the preview focus from Concrete Carnival.','Sticker Wall traces the emotional contour of concrete carnival in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(44,9,'No Permit','concrete-carnival-no-permit',4,323,'No Permit is the preview focus from Concrete Carnival.','No Permit traces the emotional contour of concrete carnival in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(45,9,'Two Minute Exit','concrete-carnival-two-minute-exit',5,182,'Two Minute Exit is the preview focus from Concrete Carnival.','Two Minute Exit traces the emotional contour of concrete carnival in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(46,10,'Median Strip','siren-economy-median-strip',1,257,'Median Strip is the preview focus from Siren Economy.','Median Strip traces the emotional contour of siren economy in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(47,10,'Siren Economy','siren-economy-siren-economy',2,286,'Siren Economy is the preview focus from Siren Economy.','Siren Economy traces the emotional contour of siren economy in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(48,10,'Paper Badge','siren-economy-paper-badge',3,315,'Paper Badge is the preview focus from Siren Economy.','Paper Badge traces the emotional contour of siren economy in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(49,10,'Turn the Bolts','siren-economy-turn-the-bolts',4,174,'Turn the Bolts is the preview focus from Siren Economy.','Turn the Bolts traces the emotional contour of siren economy in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(50,10,'Close the Gate','siren-economy-close-the-gate',5,203,'Close the Gate is the preview focus from Siren Economy.','Close the Gate traces the emotional contour of siren economy in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(51,11,'Signal Debt','signal-debt-signal-debt',1,249,'Signal Debt is the preview focus from Signal Debt.','Signal Debt traces the emotional contour of signal debt in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(52,11,'Median Palm','signal-debt-median-palm',2,278,'Median Palm is the preview focus from Signal Debt.','Median Palm traces the emotional contour of signal debt in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(53,11,'Overpass Dialtone','signal-debt-overpass-dialtone',3,307,'Overpass Dialtone is the preview focus from Signal Debt.','Overpass Dialtone traces the emotional contour of signal debt in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(54,11,'Small Claims','signal-debt-small-claims',4,166,'Small Claims is the preview focus from Signal Debt.','Small Claims traces the emotional contour of signal debt in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(55,11,'Interchange Prayer','signal-debt-interchange-prayer',5,195,'Interchange Prayer is the preview focus from Signal Debt.','Interchange Prayer traces the emotional contour of signal debt in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(56,12,'Rollout Plan','blueprint-fever-rollout-plan',1,270,'Rollout Plan is the preview focus from Blueprint Fever.','Rollout Plan traces the emotional contour of blueprint fever in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(57,12,'Blueprint Fever','blueprint-fever-blueprint-fever',2,299,'Blueprint Fever is the preview focus from Blueprint Fever.','Blueprint Fever traces the emotional contour of blueprint fever in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(58,12,'Room Tone','blueprint-fever-room-tone',3,158,'Room Tone is the preview focus from Blueprint Fever.','Room Tone traces the emotional contour of blueprint fever in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(59,12,'Silver Marker','blueprint-fever-silver-marker',4,187,'Silver Marker is the preview focus from Blueprint Fever.','Silver Marker traces the emotional contour of blueprint fever in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(60,12,'Exit Column','blueprint-fever-exit-column',5,216,'Exit Column is the preview focus from Blueprint Fever.','Exit Column traces the emotional contour of blueprint fever in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(61,13,'Blue Hour Broadcast','blue-hour-broadcast-blue-hour-broadcast',1,262,'Blue Hour Broadcast is the preview focus from Blue Hour Broadcast.','Blue Hour Broadcast traces the emotional contour of blue hour broadcast in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(62,13,'Canal Echo','blue-hour-broadcast-canal-echo',2,291,'Canal Echo is the preview focus from Blue Hour Broadcast.','Canal Echo traces the emotional contour of blue hour broadcast in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(63,13,'Fifth Table','blue-hour-broadcast-fifth-table',3,320,'Fifth Table is the preview focus from Blue Hour Broadcast.','Fifth Table traces the emotional contour of blue hour broadcast in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(64,13,'Smoke Ladder','blue-hour-broadcast-smoke-ladder',4,179,'Smoke Ladder is the preview focus from Blue Hour Broadcast.','Smoke Ladder traces the emotional contour of blue hour broadcast in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(65,13,'After Set Receipt','blue-hour-broadcast-after-set-receipt',5,208,'After Set Receipt is the preview focus from Blue Hour Broadcast.','After Set Receipt traces the emotional contour of blue hour broadcast in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(66,14,'Lobby Mirage','lobby-mirage-lobby-mirage',1,283,'Lobby Mirage is the preview focus from Lobby Mirage.','Lobby Mirage traces the emotional contour of lobby mirage in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(67,14,'Quarter Note Rain','lobby-mirage-quarter-note-rain',2,312,'Quarter Note Rain is the preview focus from Lobby Mirage.','Quarter Note Rain traces the emotional contour of lobby mirage in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(68,14,'Overnight Guest','lobby-mirage-overnight-guest',3,171,'Overnight Guest is the preview focus from Lobby Mirage.','Overnight Guest traces the emotional contour of lobby mirage in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(69,14,'Stairwell Vibraphone','lobby-mirage-stairwell-vibraphone',4,200,'Stairwell Vibraphone is the preview focus from Lobby Mirage.','Stairwell Vibraphone traces the emotional contour of lobby mirage in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(70,14,'Quiet Receipt','lobby-mirage-quiet-receipt',5,229,'Quiet Receipt is the preview focus from Lobby Mirage.','Quiet Receipt traces the emotional contour of lobby mirage in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(71,15,'Riverlights','riverlights-riverlights',1,275,'Riverlights is the preview focus from Riverlights.','Riverlights traces the emotional contour of riverlights in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(72,15,'Fence Post August','riverlights-fence-post-august',2,304,'Fence Post August is the preview focus from Riverlights.','Fence Post August traces the emotional contour of riverlights in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(73,15,'Borrowed Kettle','riverlights-borrowed-kettle',3,163,'Borrowed Kettle is the preview focus from Riverlights.','Borrowed Kettle traces the emotional contour of riverlights in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(74,15,'Downwind Choir','riverlights-downwind-choir',4,192,'Downwind Choir is the preview focus from Riverlights.','Downwind Choir traces the emotional contour of riverlights in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(75,15,'Common Thread','riverlights-common-thread',5,221,'Common Thread is the preview focus from Riverlights.','Common Thread traces the emotional contour of riverlights in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(76,16,'Handrail','common-thread-handrail',1,296,'Handrail is the preview focus from Common Thread.','Handrail traces the emotional contour of common thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(77,16,'Common Thread','common-thread-common-thread',2,155,'Common Thread is the preview focus from Common Thread.','Common Thread traces the emotional contour of common thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(78,16,'Old Union Hall','common-thread-old-union-hall',3,184,'Old Union Hall is the preview focus from Common Thread.','Old Union Hall traces the emotional contour of common thread in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(79,16,'Weather Note','common-thread-weather-note',4,213,'Weather Note is the preview focus from Common Thread.','Weather Note traces the emotional contour of common thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(80,16,'West Creek','common-thread-west-creek',5,242,'West Creek is the preview focus from Common Thread.','West Creek traces the emotional contour of common thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(81,17,'Bell Ash','iron-sleep-bell-ash',1,288,'Bell Ash is the preview focus from Iron Sleep.','Bell Ash traces the emotional contour of iron sleep in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(82,17,'Iron Sleep','iron-sleep-iron-sleep',2,317,'Iron Sleep is the preview focus from Iron Sleep.','Iron Sleep traces the emotional contour of iron sleep in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(83,17,'Procession Stair','iron-sleep-procession-stair',3,176,'Procession Stair is the preview focus from Iron Sleep.','Procession Stair traces the emotional contour of iron sleep in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(84,17,'Shutter Psalm','iron-sleep-shutter-psalm',4,205,'Shutter Psalm is the preview focus from Iron Sleep.','Shutter Psalm traces the emotional contour of iron sleep in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(85,17,'Ember Chapel','iron-sleep-ember-chapel',5,234,'Ember Chapel is the preview focus from Iron Sleep.','Ember Chapel traces the emotional contour of iron sleep in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(86,18,'Noisework','saint-of-noise-noisework',1,309,'Noisework is the preview focus from Saint of Noise.','Noisework traces the emotional contour of saint of noise in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(87,18,'Saint of Noise','saint-of-noise-saint-of-noise',2,168,'Saint of Noise is the preview focus from Saint of Noise.','Saint of Noise traces the emotional contour of saint of noise in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(88,18,'Window Soot','saint-of-noise-window-soot',3,197,'Window Soot is the preview focus from Saint of Noise.','Window Soot traces the emotional contour of saint of noise in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(89,18,'Tower Rain','saint-of-noise-tower-rain',4,226,'Tower Rain is the preview focus from Saint of Noise.','Tower Rain traces the emotional contour of saint of noise in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(90,18,'Rust Halo','saint-of-noise-rust-halo',5,255,'Rust Halo is the preview focus from Saint of Noise.','Rust Halo traces the emotional contour of saint of noise in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(91,19,'Elastic Hearts','elastic-hearts-elastic-hearts',1,301,'Elastic Hearts is the preview focus from Elastic Hearts.','Elastic Hearts traces the emotional contour of elastic hearts in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(92,19,'Flicker Map','elastic-hearts-flicker-map',2,160,'Flicker Map is the preview focus from Elastic Hearts.','Flicker Map traces the emotional contour of elastic hearts in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(93,19,'Checkout Lights','elastic-hearts-checkout-lights',3,189,'Checkout Lights is the preview focus from Elastic Hearts.','Checkout Lights traces the emotional contour of elastic hearts in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(94,19,'Half Fare','elastic-hearts-half-fare',4,218,'Half Fare is the preview focus from Elastic Hearts.','Half Fare traces the emotional contour of elastic hearts in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(95,19,'Aftercare FM','elastic-hearts-aftercare-fm',5,247,'Aftercare FM is the preview focus from Elastic Hearts.','Aftercare FM traces the emotional contour of elastic hearts in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(96,20,'Mirror Mosaic','mirror-mosaic-mirror-mosaic',1,322,'Mirror Mosaic is the preview focus from Mirror Mosaic.','Mirror Mosaic traces the emotional contour of mirror mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(97,20,'South Loop','mirror-mosaic-south-loop',2,181,'South Loop is the preview focus from Mirror Mosaic.','South Loop traces the emotional contour of mirror mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(98,20,'Cab Floor Glitter','mirror-mosaic-cab-floor-glitter',3,210,'Cab Floor Glitter is the preview focus from Mirror Mosaic.','Cab Floor Glitter traces the emotional contour of mirror mosaic in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(99,20,'Rain Delay','mirror-mosaic-rain-delay',4,239,'Rain Delay is the preview focus from Mirror Mosaic.','Rain Delay traces the emotional contour of mirror mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(100,20,'Window Waltz','mirror-mosaic-window-waltz',5,268,'Window Waltz is the preview focus from Mirror Mosaic.','Window Waltz traces the emotional contour of mirror mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(101,21,'Resin Language','resin-language-resin-language',1,314,'Resin Language is the preview focus from Resin Language.','Resin Language traces the emotional contour of resin language in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(102,21,'Circuit Teeth','resin-language-circuit-teeth',2,173,'Circuit Teeth is the preview focus from Resin Language.','Circuit Teeth traces the emotional contour of resin language in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(103,21,'Broken Caption','resin-language-broken-caption',3,202,'Broken Caption is the preview focus from Resin Language.','Broken Caption traces the emotional contour of resin language in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(104,21,'Choir Exit','resin-language-choir-exit',4,231,'Choir Exit is the preview focus from Resin Language.','Choir Exit traces the emotional contour of resin language in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(105,21,'Warm Static','resin-language-warm-static',5,260,'Warm Static is the preview focus from Resin Language.','Warm Static traces the emotional contour of resin language in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(106,22,'Fault Choir','fault-choir-fault-choir',1,165,'Fault Choir is the preview focus from Fault Choir.','Fault Choir traces the emotional contour of fault choir in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(107,22,'Signal Prayer','fault-choir-signal-prayer',2,194,'Signal Prayer is the preview focus from Fault Choir.','Signal Prayer traces the emotional contour of fault choir in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(108,22,'Paper Mouth','fault-choir-paper-mouth',3,223,'Paper Mouth is the preview focus from Fault Choir.','Paper Mouth traces the emotional contour of fault choir in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(109,22,'Room Dust','fault-choir-room-dust',4,252,'Room Dust is the preview focus from Fault Choir.','Room Dust traces the emotional contour of fault choir in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(110,22,'Small Collapse','fault-choir-small-collapse',5,281,'Small Collapse is the preview focus from Fault Choir.','Small Collapse traces the emotional contour of fault choir in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(111,23,'Harbor Burn','harbor-burn-harbor-burn',1,157,'Harbor Burn is the preview focus from Harbor Burn.','Harbor Burn traces the emotional contour of harbor burn in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(112,23,'Median Gold','harbor-burn-median-gold',2,186,'Median Gold is the preview focus from Harbor Burn.','Median Gold traces the emotional contour of harbor burn in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(113,23,'Glass Toll','harbor-burn-glass-toll',3,215,'Glass Toll is the preview focus from Harbor Burn.','Glass Toll traces the emotional contour of harbor burn in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(114,23,'Breaker Motel','harbor-burn-breaker-motel',4,244,'Breaker Motel is the preview focus from Harbor Burn.','Breaker Motel traces the emotional contour of harbor burn in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(115,23,'Wide Exit','harbor-burn-wide-exit',5,273,'Wide Exit is the preview focus from Harbor Burn.','Wide Exit traces the emotional contour of harbor burn in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(116,24,'Quiet Engine','quiet-engine-quiet-engine',1,178,'Quiet Engine is the preview focus from Quiet Engine.','Quiet Engine traces the emotional contour of quiet engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(117,24,'Chrome Valley','quiet-engine-chrome-valley',2,207,'Chrome Valley is the preview focus from Quiet Engine.','Chrome Valley traces the emotional contour of quiet engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(118,24,'Heat Map','quiet-engine-heat-map',3,236,'Heat Map is the preview focus from Quiet Engine.','Heat Map traces the emotional contour of quiet engine in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(119,24,'August Freight','quiet-engine-august-freight',4,265,'August Freight is the preview focus from Quiet Engine.','August Freight traces the emotional contour of quiet engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(120,24,'Left Signal','quiet-engine-left-signal',5,294,'Left Signal is the preview focus from Quiet Engine.','Left Signal traces the emotional contour of quiet engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(121,25,'Static Weather','static-weather-static-weather',1,170,'Static Weather is the preview focus from Static Weather.','Static Weather traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(122,25,'Platform Map','static-weather-platform-map',2,199,'Platform Map is the preview focus from Static Weather.','Platform Map traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(123,25,'August Ledger','static-weather-august-ledger',3,228,'August Ledger is the preview focus from Static Weather.','August Ledger traces the emotional contour of static weather in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(124,25,'Pattern Glow','static-weather-pattern-glow',4,257,'Pattern Glow is the preview focus from Static Weather.','Pattern Glow traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(125,25,'Window Transit','static-weather-window-transit',5,286,'Window Transit is the preview focus from Static Weather.','Window Transit traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(126,26,'Anchor Weather','quiet-vector-anchor-weather',1,191,'Anchor Weather is the preview focus from Quiet Vector.','Anchor Weather traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(127,26,'Static Map','quiet-vector-static-map',2,220,'Static Map is the preview focus from Quiet Vector.','Static Map traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(128,26,'Platform Ledger','quiet-vector-platform-ledger',3,249,'Platform Ledger is the preview focus from Quiet Vector.','Platform Ledger traces the emotional contour of quiet vector in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(129,26,'August Glow','quiet-vector-august-glow',4,278,'August Glow is the preview focus from Quiet Vector.','August Glow traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(130,26,'Pattern Transit','quiet-vector-pattern-transit',5,307,'Pattern Transit is the preview focus from Quiet Vector.','Pattern Transit traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(131,27,'Transfer Note','harbor-ledger-transfer-note',1,183,'Transfer Note is the preview focus from Harbor Ledger.','Transfer Note traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(132,27,'Rain Line','harbor-ledger-rain-line',2,212,'Rain Line is the preview focus from Harbor Ledger.','Rain Line traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(133,27,'Invoice Receipt','harbor-ledger-invoice-receipt',3,241,'Invoice Receipt is the preview focus from Harbor Ledger.','Invoice Receipt traces the emotional contour of harbor ledger in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(134,27,'Current Dust','harbor-ledger-current-dust',4,270,'Current Dust is the preview focus from Harbor Ledger.','Current Dust traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(135,27,'Median Dialtone','harbor-ledger-median-dialtone',5,299,'Median Dialtone is the preview focus from Harbor Ledger.','Median Dialtone traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(136,28,'Anchor Map','paper-thread-anchor-map',1,204,'Anchor Map is the preview focus from Paper Thread.','Anchor Map traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(137,28,'Static Ledger','paper-thread-static-ledger',2,233,'Static Ledger is the preview focus from Paper Thread.','Static Ledger traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(138,28,'Platform Glow','paper-thread-platform-glow',3,262,'Platform Glow is the preview focus from Paper Thread.','Platform Glow traces the emotional contour of paper thread in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(139,28,'August Transit','paper-thread-august-transit',4,291,'August Transit is the preview focus from Paper Thread.','August Transit traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(140,28,'Pattern Machine','paper-thread-pattern-machine',5,320,'Pattern Machine is the preview focus from Paper Thread.','Pattern Machine traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(141,29,'Platform Glow','river-cinema-platform-glow',1,196,'Platform Glow is the preview focus from River Cinema.','Platform Glow traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(142,29,'August Transit','river-cinema-august-transit',2,225,'August Transit is the preview focus from River Cinema.','August Transit traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(143,29,'Pattern Machine','river-cinema-pattern-machine',3,254,'Pattern Machine is the preview focus from River Cinema.','Pattern Machine traces the emotional contour of river cinema in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(144,29,'Window Murmur','river-cinema-window-murmur',4,283,'Window Murmur is the preview focus from River Cinema.','Window Murmur traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(145,29,'Breaker Light','river-cinema-breaker-light',5,312,'Breaker Light is the preview focus from River Cinema.','Breaker Light traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(146,30,'Median Signal','chrome-parade-median-signal',1,217,'Median Signal is the preview focus from Chrome Parade.','Median Signal traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(147,30,'Receipt Weather','chrome-parade-receipt-weather',2,246,'Receipt Weather is the preview focus from Chrome Parade.','Receipt Weather traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(148,30,'Basin Map','chrome-parade-basin-map',3,275,'Basin Map is the preview focus from Chrome Parade.','Basin Map traces the emotional contour of chrome parade in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(149,30,'Anchor Ledger','chrome-parade-anchor-ledger',4,304,'Anchor Ledger is the preview focus from Chrome Parade.','Anchor Ledger traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(150,30,'Static Glow','chrome-parade-static-glow',5,163,'Static Glow is the preview focus from Chrome Parade.','Static Glow traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(151,31,'Receipt Weather','signal-method-receipt-weather',1,209,'Receipt Weather is the preview focus from Signal Method.','Receipt Weather traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(152,31,'Basin Map','signal-method-basin-map',2,238,'Basin Map is the preview focus from Signal Method.','Basin Map traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(153,31,'Anchor Ledger','signal-method-anchor-ledger',3,267,'Anchor Ledger is the preview focus from Signal Method.','Anchor Ledger traces the emotional contour of signal method in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(154,31,'Static Glow','signal-method-static-glow',4,296,'Static Glow is the preview focus from Signal Method.','Static Glow traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(155,31,'Platform Transit','signal-method-platform-transit',5,155,'Platform Transit is the preview focus from Signal Method.','Platform Transit traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(156,32,'Transfer Dust','south-engine-transfer-dust',1,230,'Transfer Dust is the preview focus from South Engine.','Transfer Dust traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(157,32,'Rain Dialtone','south-engine-rain-dialtone',2,259,'Rain Dialtone is the preview focus from South Engine.','Rain Dialtone traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(158,32,'Invoice Index','south-engine-invoice-index',3,288,'Invoice Index is the preview focus from South Engine.','Invoice Index traces the emotional contour of south engine in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(159,32,'Current Signal','south-engine-current-signal',4,317,'Current Signal is the preview focus from South Engine.','Current Signal traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(160,32,'Median Weather','south-engine-median-weather',5,176,'Median Weather is the preview focus from South Engine.','Median Weather traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(161,33,'Transfer Dust','blue-current-transfer-dust',1,222,'Transfer Dust is the preview focus from Blue Current.','Transfer Dust traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(162,33,'Rain Dialtone','blue-current-rain-dialtone',2,251,'Rain Dialtone is the preview focus from Blue Current.','Rain Dialtone traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(163,33,'Invoice Index','blue-current-invoice-index',3,280,'Invoice Index is the preview focus from Blue Current.','Invoice Index traces the emotional contour of blue current in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(164,33,'Current Signal','blue-current-current-signal',4,309,'Current Signal is the preview focus from Blue Current.','Current Signal traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(165,33,'Median Weather','blue-current-median-weather',5,168,'Median Weather is the preview focus from Blue Current.','Median Weather traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(166,34,'Invoice Signal','midnight-signal-invoice-signal',1,243,'Invoice Signal is the preview focus from Midnight Signal.','Invoice Signal traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(167,34,'Current Weather','midnight-signal-current-weather',2,272,'Current Weather is the preview focus from Midnight Signal.','Current Weather traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(168,34,'Median Map','midnight-signal-median-map',3,301,'Median Map is the preview focus from Midnight Signal.','Median Map traces the emotional contour of midnight signal in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(169,34,'Receipt Ledger','midnight-signal-receipt-ledger',4,160,'Receipt Ledger is the preview focus from Midnight Signal.','Receipt Ledger traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(170,34,'Basin Glow','midnight-signal-basin-glow',5,189,'Basin Glow is the preview focus from Midnight Signal.','Basin Glow traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(171,35,'August Light','late-boulevard-august-light',1,235,'August Light is the preview focus from Late Boulevard.','August Light traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(172,35,'Pattern Note','late-boulevard-pattern-note',2,264,'Pattern Note is the preview focus from Late Boulevard.','Pattern Note traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(173,35,'Window Line','late-boulevard-window-line',3,293,'Window Line is the preview focus from Late Boulevard.','Window Line traces the emotional contour of late boulevard in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(174,35,'Breaker Receipt','late-boulevard-breaker-receipt',4,322,'Breaker Receipt is the preview focus from Late Boulevard.','Breaker Receipt traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(175,35,'Hallway Dust','late-boulevard-hallway-dust',5,181,'Hallway Dust is the preview focus from Late Boulevard.','Hallway Dust traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(176,36,'Basin Transit','glass-mosaic-basin-transit',1,256,'Basin Transit is the preview focus from Glass Mosaic.','Basin Transit traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(177,36,'Anchor Machine','glass-mosaic-anchor-machine',2,285,'Anchor Machine is the preview focus from Glass Mosaic.','Anchor Machine traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(178,36,'Static Murmur','glass-mosaic-static-murmur',3,314,'Static Murmur is the preview focus from Glass Mosaic.','Static Murmur traces the emotional contour of glass mosaic in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(179,36,'Platform Light','glass-mosaic-platform-light',4,173,'Platform Light is the preview focus from Glass Mosaic.','Platform Light traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(180,36,'August Note','glass-mosaic-august-note',5,202,'August Note is the preview focus from Glass Mosaic.','August Note traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(181,37,'August Note','golden-garden-august-note',1,248,'August Note is the preview focus from Golden Garden.','August Note traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(182,37,'Pattern Line','golden-garden-pattern-line',2,277,'Pattern Line is the preview focus from Golden Garden.','Pattern Line traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(183,37,'Window Receipt','golden-garden-window-receipt',3,306,'Window Receipt is the preview focus from Golden Garden.','Window Receipt traces the emotional contour of golden garden in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(184,37,'Breaker Dust','golden-garden-breaker-dust',4,165,'Breaker Dust is the preview focus from Golden Garden.','Breaker Dust traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(185,37,'Hallway Dialtone','golden-garden-hallway-dialtone',5,194,'Hallway Dialtone is the preview focus from Golden Garden.','Hallway Dialtone traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(186,38,'Pattern Receipt','motel-harbor-pattern-receipt',1,269,'Pattern Receipt is the preview focus from Motel Harbor.','Pattern Receipt traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(187,38,'Window Dust','motel-harbor-window-dust',2,298,'Window Dust is the preview focus from Motel Harbor.','Window Dust traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(188,38,'Breaker Dialtone','motel-harbor-breaker-dialtone',3,157,'Breaker Dialtone is the preview focus from Motel Harbor.','Breaker Dialtone traces the emotional contour of motel harbor in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(189,38,'Hallway Index','motel-harbor-hallway-index',4,186,'Hallway Index is the preview focus from Motel Harbor.','Hallway Index traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(190,38,'Transfer Signal','motel-harbor-transfer-signal',5,215,'Transfer Signal is the preview focus from Motel Harbor.','Transfer Signal traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(191,39,'Anchor Murmur','quiet-transit-anchor-murmur',1,261,'Anchor Murmur is the preview focus from Quiet Transit.','Anchor Murmur traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(192,39,'Static Light','quiet-transit-static-light',2,290,'Static Light is the preview focus from Quiet Transit.','Static Light traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(193,39,'Platform Note','quiet-transit-platform-note',3,319,'Platform Note is the preview focus from Quiet Transit.','Platform Note traces the emotional contour of quiet transit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(194,39,'August Line','quiet-transit-august-line',4,178,'August Line is the preview focus from Quiet Transit.','August Line traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(195,39,'Pattern Receipt','quiet-transit-pattern-receipt',5,207,'Pattern Receipt is the preview focus from Quiet Transit.','Pattern Receipt traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(196,40,'August Receipt','stone-circuit-august-receipt',1,282,'August Receipt is the preview focus from Stone Circuit.','August Receipt traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(197,40,'Pattern Dust','stone-circuit-pattern-dust',2,311,'Pattern Dust is the preview focus from Stone Circuit.','Pattern Dust traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(198,40,'Window Dialtone','stone-circuit-window-dialtone',3,170,'Window Dialtone is the preview focus from Stone Circuit.','Window Dialtone traces the emotional contour of stone circuit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(199,40,'Breaker Index','stone-circuit-breaker-index',4,199,'Breaker Index is the preview focus from Stone Circuit.','Breaker Index traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(200,40,'Hallway Signal','stone-circuit-hallway-signal',5,228,'Hallway Signal is the preview focus from Stone Circuit.','Hallway Signal traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(201,41,'Breaker Index','paper-archive-breaker-index',1,274,'Breaker Index is the preview focus from Paper Archive.','Breaker Index traces the emotional contour of paper archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(202,41,'Hallway Signal','paper-archive-hallway-signal',2,303,'Hallway Signal is the preview focus from Paper Archive.','Hallway Signal traces the emotional contour of paper archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(203,41,'Transfer Weather','paper-archive-transfer-weather',3,162,'Transfer Weather is the preview focus from Paper Archive.','Transfer Weather traces the emotional contour of paper archive in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(204,41,'Rain Map','paper-archive-rain-map',4,191,'Rain Map is the preview focus from Paper Archive.','Rain Map traces the emotional contour of paper archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(205,41,'Invoice Ledger','paper-archive-invoice-ledger',5,220,'Invoice Ledger is the preview focus from Paper Archive.','Invoice Ledger traces the emotional contour of paper archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(206,42,'Window Index','delta-minutes-window-index',1,295,'Window Index is the preview focus from Delta Minutes.','Window Index traces the emotional contour of delta minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(207,42,'Breaker Signal','delta-minutes-breaker-signal',2,324,'Breaker Signal is the preview focus from Delta Minutes.','Breaker Signal traces the emotional contour of delta minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(208,42,'Hallway Weather','delta-minutes-hallway-weather',3,183,'Hallway Weather is the preview focus from Delta Minutes.','Hallway Weather traces the emotional contour of delta minutes in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(209,42,'Transfer Map','delta-minutes-transfer-map',4,212,'Transfer Map is the preview focus from Delta Minutes.','Transfer Map traces the emotional contour of delta minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(210,42,'Rain Ledger','delta-minutes-rain-ledger',5,241,'Rain Ledger is the preview focus from Delta Minutes.','Rain Ledger traces the emotional contour of delta minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(211,43,'Median Machine','chrome-pattern-median-machine',1,287,'Median Machine is the preview focus from Chrome Pattern.','Median Machine traces the emotional contour of chrome pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(212,43,'Receipt Murmur','chrome-pattern-receipt-murmur',2,316,'Receipt Murmur is the preview focus from Chrome Pattern.','Receipt Murmur traces the emotional contour of chrome pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(213,43,'Basin Light','chrome-pattern-basin-light',3,175,'Basin Light is the preview focus from Chrome Pattern.','Basin Light traces the emotional contour of chrome pattern in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(214,43,'Anchor Note','chrome-pattern-anchor-note',4,204,'Anchor Note is the preview focus from Chrome Pattern.','Anchor Note traces the emotional contour of chrome pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(215,43,'Static Line','chrome-pattern-static-line',5,233,'Static Line is the preview focus from Chrome Pattern.','Static Line traces the emotional contour of chrome pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(216,44,'Window Signal','velvet-weather-window-signal',1,308,'Window Signal is the preview focus from Velvet Weather.','Window Signal traces the emotional contour of velvet weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(217,44,'Breaker Weather','velvet-weather-breaker-weather',2,167,'Breaker Weather is the preview focus from Velvet Weather.','Breaker Weather traces the emotional contour of velvet weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(218,44,'Hallway Map','velvet-weather-hallway-map',3,196,'Hallway Map is the preview focus from Velvet Weather.','Hallway Map traces the emotional contour of velvet weather in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(219,44,'Transfer Ledger','velvet-weather-transfer-ledger',4,225,'Transfer Ledger is the preview focus from Velvet Weather.','Transfer Ledger traces the emotional contour of velvet weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(220,44,'Rain Glow','velvet-weather-rain-glow',5,254,'Rain Glow is the preview focus from Velvet Weather.','Rain Glow traces the emotional contour of velvet weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(221,45,'Receipt Light','south-dusk-receipt-light',1,300,'Receipt Light is the preview focus from South Dusk.','Receipt Light traces the emotional contour of south dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(222,45,'Basin Note','south-dusk-basin-note',2,159,'Basin Note is the preview focus from South Dusk.','Basin Note traces the emotional contour of south dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(223,45,'Anchor Line','south-dusk-anchor-line',3,188,'Anchor Line is the preview focus from South Dusk.','Anchor Line traces the emotional contour of south dusk in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(224,45,'Static Receipt','south-dusk-static-receipt',4,217,'Static Receipt is the preview focus from South Dusk.','Static Receipt traces the emotional contour of south dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(225,45,'Platform Dust','south-dusk-platform-dust',5,246,'Platform Dust is the preview focus from South Dusk.','Platform Dust traces the emotional contour of south dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(226,46,'Static Dust','open-ledger-static-dust',1,321,'Static Dust is the preview focus from Open Ledger.','Static Dust traces the emotional contour of open ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(227,46,'Platform Dialtone','open-ledger-platform-dialtone',2,180,'Platform Dialtone is the preview focus from Open Ledger.','Platform Dialtone traces the emotional contour of open ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(228,46,'August Index','open-ledger-august-index',3,209,'August Index is the preview focus from Open Ledger.','August Index traces the emotional contour of open ledger in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(229,46,'Pattern Signal','open-ledger-pattern-signal',4,238,'Pattern Signal is the preview focus from Open Ledger.','Pattern Signal traces the emotional contour of open ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(230,46,'Window Weather','open-ledger-window-weather',5,267,'Window Weather is the preview focus from Open Ledger.','Window Weather traces the emotional contour of open ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(231,47,'Basin Line','midnight-vector-basin-line',1,313,'Basin Line is the preview focus from Midnight Vector.','Basin Line traces the emotional contour of midnight vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(232,47,'Anchor Receipt','midnight-vector-anchor-receipt',2,172,'Anchor Receipt is the preview focus from Midnight Vector.','Anchor Receipt traces the emotional contour of midnight vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(233,47,'Static Dust','midnight-vector-static-dust',3,201,'Static Dust is the preview focus from Midnight Vector.','Static Dust traces the emotional contour of midnight vector in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(234,47,'Platform Dialtone','midnight-vector-platform-dialtone',4,230,'Platform Dialtone is the preview focus from Midnight Vector.','Platform Dialtone traces the emotional contour of midnight vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(235,47,'August Index','midnight-vector-august-index',5,259,'August Index is the preview focus from Midnight Vector.','August Index traces the emotional contour of midnight vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(236,48,'Pattern Weather','after-cinema-pattern-weather',1,164,'Pattern Weather is the preview focus from After Cinema.','Pattern Weather traces the emotional contour of after cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(237,48,'Window Map','after-cinema-window-map',2,193,'Window Map is the preview focus from After Cinema.','Window Map traces the emotional contour of after cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(238,48,'Breaker Ledger','after-cinema-breaker-ledger',3,222,'Breaker Ledger is the preview focus from After Cinema.','Breaker Ledger traces the emotional contour of after cinema in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(239,48,'Hallway Glow','after-cinema-hallway-glow',4,251,'Hallway Glow is the preview focus from After Cinema.','Hallway Glow traces the emotional contour of after cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(240,48,'Transfer Transit','after-cinema-transfer-transit',5,280,'Transfer Transit is the preview focus from After Cinema.','Transfer Transit traces the emotional contour of after cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(241,49,'Hallway Glow','glass-thread-hallway-glow',1,156,'Hallway Glow is the preview focus from Glass Thread.','Hallway Glow traces the emotional contour of glass thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(242,49,'Transfer Transit','glass-thread-transfer-transit',2,185,'Transfer Transit is the preview focus from Glass Thread.','Transfer Transit traces the emotional contour of glass thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(243,49,'Rain Machine','glass-thread-rain-machine',3,214,'Rain Machine is the preview focus from Glass Thread.','Rain Machine traces the emotional contour of glass thread in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(244,49,'Invoice Murmur','glass-thread-invoice-murmur',4,243,'Invoice Murmur is the preview focus from Glass Thread.','Invoice Murmur traces the emotional contour of glass thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(245,49,'Current Light','glass-thread-current-light',5,272,'Current Light is the preview focus from Glass Thread.','Current Light traces the emotional contour of glass thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(246,50,'August Weather','broken-method-august-weather',1,177,'August Weather is the preview focus from Broken Method.','August Weather traces the emotional contour of broken method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(247,50,'Pattern Map','broken-method-pattern-map',2,206,'Pattern Map is the preview focus from Broken Method.','Pattern Map traces the emotional contour of broken method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(248,50,'Window Ledger','broken-method-window-ledger',3,235,'Window Ledger is the preview focus from Broken Method.','Window Ledger traces the emotional contour of broken method in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(249,50,'Breaker Glow','broken-method-breaker-glow',4,264,'Breaker Glow is the preview focus from Broken Method.','Breaker Glow traces the emotional contour of broken method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(250,50,'Hallway Transit','broken-method-hallway-transit',5,293,'Hallway Transit is the preview focus from Broken Method.','Hallway Transit traces the emotional contour of broken method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(251,51,'Basin Dust','motel-parade-basin-dust',1,169,'Basin Dust is the preview focus from Motel Parade.','Basin Dust traces the emotional contour of motel parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(252,51,'Anchor Dialtone','motel-parade-anchor-dialtone',2,198,'Anchor Dialtone is the preview focus from Motel Parade.','Anchor Dialtone traces the emotional contour of motel parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(253,51,'Static Index','motel-parade-static-index',3,227,'Static Index is the preview focus from Motel Parade.','Static Index traces the emotional contour of motel parade in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(254,51,'Platform Signal','motel-parade-platform-signal',4,256,'Platform Signal is the preview focus from Motel Parade.','Platform Signal traces the emotional contour of motel parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(255,51,'August Weather','motel-parade-august-weather',5,285,'August Weather is the preview focus from Motel Parade.','August Weather traces the emotional contour of motel parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(256,52,'Invoice Note','static-current-invoice-note',1,190,'Invoice Note is the preview focus from Static Current.','Invoice Note traces the emotional contour of static current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(257,52,'Current Line','static-current-current-line',2,219,'Current Line is the preview focus from Static Current.','Current Line traces the emotional contour of static current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(258,52,'Median Receipt','static-current-median-receipt',3,248,'Median Receipt is the preview focus from Static Current.','Median Receipt traces the emotional contour of static current in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(259,52,'Receipt Dust','static-current-receipt-dust',4,277,'Receipt Dust is the preview focus from Static Current.','Receipt Dust traces the emotional contour of static current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(260,52,'Basin Dialtone','static-current-basin-dialtone',5,306,'Basin Dialtone is the preview focus from Static Current.','Basin Dialtone traces the emotional contour of static current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(261,53,'August Map','stone-engine-august-map',1,182,'August Map is the preview focus from Stone Engine.','August Map traces the emotional contour of stone engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(262,53,'Pattern Ledger','stone-engine-pattern-ledger',2,211,'Pattern Ledger is the preview focus from Stone Engine.','Pattern Ledger traces the emotional contour of stone engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(263,53,'Window Glow','stone-engine-window-glow',3,240,'Window Glow is the preview focus from Stone Engine.','Window Glow traces the emotional contour of stone engine in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(264,53,'Breaker Transit','stone-engine-breaker-transit',4,269,'Breaker Transit is the preview focus from Stone Engine.','Breaker Transit traces the emotional contour of stone engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(265,53,'Hallway Machine','stone-engine-hallway-machine',5,298,'Hallway Machine is the preview focus from Stone Engine.','Hallway Machine traces the emotional contour of stone engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(266,54,'Window Transit','harbor-boulevard-window-transit',1,203,'Window Transit is the preview focus from Harbor Boulevard.','Window Transit traces the emotional contour of harbor boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(267,54,'Breaker Machine','harbor-boulevard-breaker-machine',2,232,'Breaker Machine is the preview focus from Harbor Boulevard.','Breaker Machine traces the emotional contour of harbor boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(268,54,'Hallway Murmur','harbor-boulevard-hallway-murmur',3,261,'Hallway Murmur is the preview focus from Harbor Boulevard.','Hallway Murmur traces the emotional contour of harbor boulevard in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(269,54,'Transfer Light','harbor-boulevard-transfer-light',4,290,'Transfer Light is the preview focus from Harbor Boulevard.','Transfer Light traces the emotional contour of harbor boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(270,54,'Rain Note','harbor-boulevard-rain-note',5,319,'Rain Note is the preview focus from Harbor Boulevard.','Rain Note traces the emotional contour of harbor boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(271,55,'Rain Note','delta-signal-rain-note',1,195,'Rain Note is the preview focus from Delta Signal.','Rain Note traces the emotional contour of delta signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(272,55,'Invoice Line','delta-signal-invoice-line',2,224,'Invoice Line is the preview focus from Delta Signal.','Invoice Line traces the emotional contour of delta signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(273,55,'Current Receipt','delta-signal-current-receipt',3,253,'Current Receipt is the preview focus from Delta Signal.','Current Receipt traces the emotional contour of delta signal in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(274,55,'Median Dust','delta-signal-median-dust',4,282,'Median Dust is the preview focus from Delta Signal.','Median Dust traces the emotional contour of delta signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(275,55,'Receipt Dialtone','delta-signal-receipt-dialtone',5,311,'Receipt Dialtone is the preview focus from Delta Signal.','Receipt Dialtone traces the emotional contour of delta signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(276,56,'Anchor Weather','river-garden-anchor-weather',1,216,'Anchor Weather is the preview focus from River Garden.','Anchor Weather traces the emotional contour of river garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(277,56,'Static Map','river-garden-static-map',2,245,'Static Map is the preview focus from River Garden.','Static Map traces the emotional contour of river garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(278,56,'Platform Ledger','river-garden-platform-ledger',3,274,'Platform Ledger is the preview focus from River Garden.','Platform Ledger traces the emotional contour of river garden in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(279,56,'August Glow','river-garden-august-glow',4,303,'August Glow is the preview focus from River Garden.','August Glow traces the emotional contour of river garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(280,56,'Pattern Transit','river-garden-pattern-transit',5,162,'Pattern Transit is the preview focus from River Garden.','Pattern Transit traces the emotional contour of river garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(281,57,'Anchor Weather','velvet-mosaic-anchor-weather',1,208,'Anchor Weather is the preview focus from Velvet Mosaic.','Anchor Weather traces the emotional contour of velvet mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(282,57,'Static Map','velvet-mosaic-static-map',2,237,'Static Map is the preview focus from Velvet Mosaic.','Static Map traces the emotional contour of velvet mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(283,57,'Platform Ledger','velvet-mosaic-platform-ledger',3,266,'Platform Ledger is the preview focus from Velvet Mosaic.','Platform Ledger traces the emotional contour of velvet mosaic in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(284,57,'August Glow','velvet-mosaic-august-glow',4,295,'August Glow is the preview focus from Velvet Mosaic.','August Glow traces the emotional contour of velvet mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(285,57,'Pattern Transit','velvet-mosaic-pattern-transit',5,324,'Pattern Transit is the preview focus from Velvet Mosaic.','Pattern Transit traces the emotional contour of velvet mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(286,58,'Hallway Note','signal-transit-hallway-note',1,229,'Hallway Note is the preview focus from Signal Transit.','Hallway Note traces the emotional contour of signal transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(287,58,'Transfer Line','signal-transit-transfer-line',2,258,'Transfer Line is the preview focus from Signal Transit.','Transfer Line traces the emotional contour of signal transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(288,58,'Rain Receipt','signal-transit-rain-receipt',3,287,'Rain Receipt is the preview focus from Signal Transit.','Rain Receipt traces the emotional contour of signal transit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(289,58,'Invoice Dust','signal-transit-invoice-dust',4,316,'Invoice Dust is the preview focus from Signal Transit.','Invoice Dust traces the emotional contour of signal transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(290,58,'Current Dialtone','signal-transit-current-dialtone',5,175,'Current Dialtone is the preview focus from Signal Transit.','Current Dialtone traces the emotional contour of signal transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(291,59,'Basin Weather','open-harbor-basin-weather',1,221,'Basin Weather is the preview focus from Open Harbor.','Basin Weather traces the emotional contour of open harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(292,59,'Anchor Map','open-harbor-anchor-map',2,250,'Anchor Map is the preview focus from Open Harbor.','Anchor Map traces the emotional contour of open harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(293,59,'Static Ledger','open-harbor-static-ledger',3,279,'Static Ledger is the preview focus from Open Harbor.','Static Ledger traces the emotional contour of open harbor in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(294,59,'Platform Glow','open-harbor-platform-glow',4,308,'Platform Glow is the preview focus from Open Harbor.','Platform Glow traces the emotional contour of open harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(295,59,'August Transit','open-harbor-august-transit',5,167,'August Transit is the preview focus from Open Harbor.','August Transit traces the emotional contour of open harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(296,60,'Hallway Line','blue-archive-hallway-line',1,242,'Hallway Line is the preview focus from Blue Archive.','Hallway Line traces the emotional contour of blue archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(297,60,'Transfer Receipt','blue-archive-transfer-receipt',2,271,'Transfer Receipt is the preview focus from Blue Archive.','Transfer Receipt traces the emotional contour of blue archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(298,60,'Rain Dust','blue-archive-rain-dust',3,300,'Rain Dust is the preview focus from Blue Archive.','Rain Dust traces the emotional contour of blue archive in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(299,60,'Invoice Dialtone','blue-archive-invoice-dialtone',4,159,'Invoice Dialtone is the preview focus from Blue Archive.','Invoice Dialtone traces the emotional contour of blue archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(300,60,'Current Index','blue-archive-current-index',5,188,'Current Index is the preview focus from Blue Archive.','Current Index traces the emotional contour of blue archive in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(301,61,'Rain Dust','after-circuit-rain-dust',1,234,'Rain Dust is the preview focus from After Circuit.','Rain Dust traces the emotional contour of after circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(302,61,'Invoice Dialtone','after-circuit-invoice-dialtone',2,263,'Invoice Dialtone is the preview focus from After Circuit.','Invoice Dialtone traces the emotional contour of after circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(303,61,'Current Index','after-circuit-current-index',3,292,'Current Index is the preview focus from After Circuit.','Current Index traces the emotional contour of after circuit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(304,61,'Median Signal','after-circuit-median-signal',4,321,'Median Signal is the preview focus from After Circuit.','Median Signal traces the emotional contour of after circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(305,61,'Receipt Weather','after-circuit-receipt-weather',5,180,'Receipt Weather is the preview focus from After Circuit.','Receipt Weather traces the emotional contour of after circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(306,62,'Window Note','late-pattern-window-note',1,255,'Window Note is the preview focus from Late Pattern.','Window Note traces the emotional contour of late pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(307,62,'Breaker Line','late-pattern-breaker-line',2,284,'Breaker Line is the preview focus from Late Pattern.','Breaker Line traces the emotional contour of late pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(308,62,'Hallway Receipt','late-pattern-hallway-receipt',3,313,'Hallway Receipt is the preview focus from Late Pattern.','Hallway Receipt traces the emotional contour of late pattern in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(309,62,'Transfer Dust','late-pattern-transfer-dust',4,172,'Transfer Dust is the preview focus from Late Pattern.','Transfer Dust traces the emotional contour of late pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(310,62,'Rain Dialtone','late-pattern-rain-dialtone',5,201,'Rain Dialtone is the preview focus from Late Pattern.','Rain Dialtone traces the emotional contour of late pattern in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(311,63,'Anchor Glow','broken-minutes-anchor-glow',1,247,'Anchor Glow is the preview focus from Broken Minutes.','Anchor Glow traces the emotional contour of broken minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(312,63,'Static Transit','broken-minutes-static-transit',2,276,'Static Transit is the preview focus from Broken Minutes.','Static Transit traces the emotional contour of broken minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(313,63,'Platform Machine','broken-minutes-platform-machine',3,305,'Platform Machine is the preview focus from Broken Minutes.','Platform Machine traces the emotional contour of broken minutes in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(314,63,'August Murmur','broken-minutes-august-murmur',4,164,'August Murmur is the preview focus from Broken Minutes.','August Murmur traces the emotional contour of broken minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(315,63,'Pattern Light','broken-minutes-pattern-light',5,193,'Pattern Light is the preview focus from Broken Minutes.','Pattern Light traces the emotional contour of broken minutes in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(316,64,'Hallway Dust','golden-dusk-hallway-dust',1,268,'Hallway Dust is the preview focus from Golden Dusk.','Hallway Dust traces the emotional contour of golden dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(317,64,'Transfer Dialtone','golden-dusk-transfer-dialtone',2,297,'Transfer Dialtone is the preview focus from Golden Dusk.','Transfer Dialtone traces the emotional contour of golden dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(318,64,'Rain Index','golden-dusk-rain-index',3,156,'Rain Index is the preview focus from Golden Dusk.','Rain Index traces the emotional contour of golden dusk in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(319,64,'Invoice Signal','golden-dusk-invoice-signal',4,185,'Invoice Signal is the preview focus from Golden Dusk.','Invoice Signal traces the emotional contour of golden dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(320,64,'Current Weather','golden-dusk-current-weather',5,214,'Current Weather is the preview focus from Golden Dusk.','Current Weather traces the emotional contour of golden dusk in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(321,65,'Breaker Receipt','static-weather-fault-parade-breaker-receipt',1,260,'Breaker Receipt is the preview focus from Static Weather.','Breaker Receipt traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(322,65,'Hallway Dust','static-weather-fault-parade-hallway-dust',2,289,'Hallway Dust is the preview focus from Static Weather.','Hallway Dust traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(323,65,'Transfer Dialtone','static-weather-fault-parade-transfer-dialtone',3,318,'Transfer Dialtone is the preview focus from Static Weather.','Transfer Dialtone traces the emotional contour of static weather in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(324,65,'Rain Index','static-weather-fault-parade-rain-index',4,177,'Rain Index is the preview focus from Static Weather.','Rain Index traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(325,65,'Invoice Signal','static-weather-fault-parade-invoice-signal',5,206,'Invoice Signal is the preview focus from Static Weather.','Invoice Signal traces the emotional contour of static weather in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(326,66,'Window Receipt','quiet-vector-fault-parade-window-receipt',1,281,'Window Receipt is the preview focus from Quiet Vector.','Window Receipt traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(327,66,'Breaker Dust','quiet-vector-fault-parade-breaker-dust',2,310,'Breaker Dust is the preview focus from Quiet Vector.','Breaker Dust traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(328,66,'Hallway Dialtone','quiet-vector-fault-parade-hallway-dialtone',3,169,'Hallway Dialtone is the preview focus from Quiet Vector.','Hallway Dialtone traces the emotional contour of quiet vector in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(329,66,'Transfer Index','quiet-vector-fault-parade-transfer-index',4,198,'Transfer Index is the preview focus from Quiet Vector.','Transfer Index traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(330,66,'Rain Signal','quiet-vector-fault-parade-rain-signal',5,227,'Rain Signal is the preview focus from Quiet Vector.','Rain Signal traces the emotional contour of quiet vector in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(331,67,'Receipt Glow','harbor-ledger-static-ledger-receipt-glow',1,273,'Receipt Glow is the preview focus from Harbor Ledger.','Receipt Glow traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(332,67,'Basin Transit','harbor-ledger-static-ledger-basin-transit',2,302,'Basin Transit is the preview focus from Harbor Ledger.','Basin Transit traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(333,67,'Anchor Machine','harbor-ledger-static-ledger-anchor-machine',3,161,'Anchor Machine is the preview focus from Harbor Ledger.','Anchor Machine traces the emotional contour of harbor ledger in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(334,67,'Static Murmur','harbor-ledger-static-ledger-static-murmur',4,190,'Static Murmur is the preview focus from Harbor Ledger.','Static Murmur traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(335,67,'Platform Light','harbor-ledger-static-ledger-platform-light',5,219,'Platform Light is the preview focus from Harbor Ledger.','Platform Light traces the emotional contour of harbor ledger in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(336,68,'Window Dust','paper-thread-static-ledger-window-dust',1,294,'Window Dust is the preview focus from Paper Thread.','Window Dust traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(337,68,'Breaker Dialtone','paper-thread-static-ledger-breaker-dialtone',2,323,'Breaker Dialtone is the preview focus from Paper Thread.','Breaker Dialtone traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(338,68,'Hallway Index','paper-thread-static-ledger-hallway-index',3,182,'Hallway Index is the preview focus from Paper Thread.','Hallway Index traces the emotional contour of paper thread in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(339,68,'Transfer Signal','paper-thread-static-ledger-transfer-signal',4,211,'Transfer Signal is the preview focus from Paper Thread.','Transfer Signal traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(340,68,'Rain Weather','paper-thread-static-ledger-rain-weather',5,240,'Rain Weather is the preview focus from Paper Thread.','Rain Weather traces the emotional contour of paper thread in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(341,69,'Hallway Index','river-cinema-stone-balcony-hallway-index',1,286,'Hallway Index is the preview focus from River Cinema.','Hallway Index traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(342,69,'Transfer Signal','river-cinema-stone-balcony-transfer-signal',2,315,'Transfer Signal is the preview focus from River Cinema.','Transfer Signal traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(343,69,'Rain Weather','river-cinema-stone-balcony-rain-weather',3,174,'Rain Weather is the preview focus from River Cinema.','Rain Weather traces the emotional contour of river cinema in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(344,69,'Invoice Map','river-cinema-stone-balcony-invoice-map',4,203,'Invoice Map is the preview focus from River Cinema.','Invoice Map traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(345,69,'Current Ledger','river-cinema-stone-balcony-current-ledger',5,232,'Current Ledger is the preview focus from River Cinema.','Current Ledger traces the emotional contour of river cinema in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(346,70,'Platform Line','chrome-parade-stone-balcony-platform-line',1,307,'Platform Line is the preview focus from Chrome Parade.','Platform Line traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(347,70,'August Receipt','chrome-parade-stone-balcony-august-receipt',2,166,'August Receipt is the preview focus from Chrome Parade.','August Receipt traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(348,70,'Pattern Dust','chrome-parade-stone-balcony-pattern-dust',3,195,'Pattern Dust is the preview focus from Chrome Parade.','Pattern Dust traces the emotional contour of chrome parade in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(349,70,'Window Dialtone','chrome-parade-stone-balcony-window-dialtone',4,224,'Window Dialtone is the preview focus from Chrome Parade.','Window Dialtone traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(350,70,'Breaker Index','chrome-parade-stone-balcony-breaker-index',5,253,'Breaker Index is the preview focus from Chrome Parade.','Breaker Index traces the emotional contour of chrome parade in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(351,71,'August Receipt','signal-method-west-transit-august-receipt',1,299,'August Receipt is the preview focus from Signal Method.','August Receipt traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(352,71,'Pattern Dust','signal-method-west-transit-pattern-dust',2,158,'Pattern Dust is the preview focus from Signal Method.','Pattern Dust traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(353,71,'Window Dialtone','signal-method-west-transit-window-dialtone',3,187,'Window Dialtone is the preview focus from Signal Method.','Window Dialtone traces the emotional contour of signal method in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(354,71,'Breaker Index','signal-method-west-transit-breaker-index',4,216,'Breaker Index is the preview focus from Signal Method.','Breaker Index traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(355,71,'Hallway Signal','signal-method-west-transit-hallway-signal',5,245,'Hallway Signal is the preview focus from Signal Method.','Hallway Signal traces the emotional contour of signal method in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(356,72,'Receipt Murmur','south-engine-west-transit-receipt-murmur',1,320,'Receipt Murmur is the preview focus from South Engine.','Receipt Murmur traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(357,72,'Basin Light','south-engine-west-transit-basin-light',2,179,'Basin Light is the preview focus from South Engine.','Basin Light traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(358,72,'Anchor Note','south-engine-west-transit-anchor-note',3,208,'Anchor Note is the preview focus from South Engine.','Anchor Note traces the emotional contour of south engine in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(359,72,'Static Line','south-engine-west-transit-static-line',4,237,'Static Line is the preview focus from South Engine.','Static Line traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(360,72,'Platform Receipt','south-engine-west-transit-platform-receipt',5,266,'Platform Receipt is the preview focus from South Engine.','Platform Receipt traces the emotional contour of south engine in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(361,73,'Receipt Murmur','blue-current-echo-dividend-receipt-murmur',1,312,'Receipt Murmur is the preview focus from Blue Current.','Receipt Murmur traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(362,73,'Basin Light','blue-current-echo-dividend-basin-light',2,171,'Basin Light is the preview focus from Blue Current.','Basin Light traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(363,73,'Anchor Note','blue-current-echo-dividend-anchor-note',3,200,'Anchor Note is the preview focus from Blue Current.','Anchor Note traces the emotional contour of blue current in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(364,73,'Static Line','blue-current-echo-dividend-static-line',4,229,'Static Line is the preview focus from Blue Current.','Static Line traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(365,73,'Platform Receipt','blue-current-echo-dividend-platform-receipt',5,258,'Platform Receipt is the preview focus from Blue Current.','Platform Receipt traces the emotional contour of blue current in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(366,74,'Anchor Line','midnight-signal-echo-dividend-anchor-line',1,163,'Anchor Line is the preview focus from Midnight Signal.','Anchor Line traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(367,74,'Static Receipt','midnight-signal-echo-dividend-static-receipt',2,192,'Static Receipt is the preview focus from Midnight Signal.','Static Receipt traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(368,74,'Platform Dust','midnight-signal-echo-dividend-platform-dust',3,221,'Platform Dust is the preview focus from Midnight Signal.','Platform Dust traces the emotional contour of midnight signal in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(369,74,'August Dialtone','midnight-signal-echo-dividend-august-dialtone',4,250,'August Dialtone is the preview focus from Midnight Signal.','August Dialtone traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(370,74,'Pattern Index','midnight-signal-echo-dividend-pattern-index',5,279,'Pattern Index is the preview focus from Midnight Signal.','Pattern Index traces the emotional contour of midnight signal in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(371,75,'Transfer Ledger','late-boulevard-cloud-bureau-transfer-ledger',1,155,'Transfer Ledger is the preview focus from Late Boulevard.','Transfer Ledger traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(372,75,'Rain Glow','late-boulevard-cloud-bureau-rain-glow',2,184,'Rain Glow is the preview focus from Late Boulevard.','Rain Glow traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(373,75,'Invoice Transit','late-boulevard-cloud-bureau-invoice-transit',3,213,'Invoice Transit is the preview focus from Late Boulevard.','Invoice Transit traces the emotional contour of late boulevard in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(374,75,'Current Machine','late-boulevard-cloud-bureau-current-machine',4,242,'Current Machine is the preview focus from Late Boulevard.','Current Machine traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(375,75,'Median Murmur','late-boulevard-cloud-bureau-median-murmur',5,271,'Median Murmur is the preview focus from Late Boulevard.','Median Murmur traces the emotional contour of late boulevard in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(376,76,'Pattern Signal','glass-mosaic-cloud-bureau-pattern-signal',1,176,'Pattern Signal is the preview focus from Glass Mosaic.','Pattern Signal traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(377,76,'Window Weather','glass-mosaic-cloud-bureau-window-weather',2,205,'Window Weather is the preview focus from Glass Mosaic.','Window Weather traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(378,76,'Breaker Map','glass-mosaic-cloud-bureau-breaker-map',3,234,'Breaker Map is the preview focus from Glass Mosaic.','Breaker Map traces the emotional contour of glass mosaic in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(379,76,'Hallway Ledger','glass-mosaic-cloud-bureau-hallway-ledger',4,263,'Hallway Ledger is the preview focus from Glass Mosaic.','Hallway Ledger traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(380,76,'Transfer Glow','glass-mosaic-cloud-bureau-transfer-glow',5,292,'Transfer Glow is the preview focus from Glass Mosaic.','Transfer Glow traces the emotional contour of glass mosaic in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(381,77,'Transfer Glow','golden-garden-ridge-cinema-transfer-glow',1,168,'Transfer Glow is the preview focus from Golden Garden.','Transfer Glow traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(382,77,'Rain Transit','golden-garden-ridge-cinema-rain-transit',2,197,'Rain Transit is the preview focus from Golden Garden.','Rain Transit traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(383,77,'Invoice Machine','golden-garden-ridge-cinema-invoice-machine',3,226,'Invoice Machine is the preview focus from Golden Garden.','Invoice Machine traces the emotional contour of golden garden in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(384,77,'Current Murmur','golden-garden-ridge-cinema-current-murmur',4,255,'Current Murmur is the preview focus from Golden Garden.','Current Murmur traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(385,77,'Median Light','golden-garden-ridge-cinema-median-light',5,284,'Median Light is the preview focus from Golden Garden.','Median Light traces the emotional contour of golden garden in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(386,78,'Rain Machine','motel-harbor-ridge-cinema-rain-machine',1,189,'Rain Machine is the preview focus from Motel Harbor.','Rain Machine traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(387,78,'Invoice Murmur','motel-harbor-ridge-cinema-invoice-murmur',2,218,'Invoice Murmur is the preview focus from Motel Harbor.','Invoice Murmur traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(388,78,'Current Light','motel-harbor-ridge-cinema-current-light',3,247,'Current Light is the preview focus from Motel Harbor.','Current Light traces the emotional contour of motel harbor in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(389,78,'Median Note','motel-harbor-ridge-cinema-median-note',4,276,'Median Note is the preview focus from Motel Harbor.','Median Note traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(390,78,'Receipt Line','motel-harbor-ridge-cinema-receipt-line',5,305,'Receipt Line is the preview focus from Motel Harbor.','Receipt Line traces the emotional contour of motel harbor in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(391,79,'Window Map','quiet-transit-hollow-method-window-map',1,181,'Window Map is the preview focus from Quiet Transit.','Window Map traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(392,79,'Breaker Ledger','quiet-transit-hollow-method-breaker-ledger',2,210,'Breaker Ledger is the preview focus from Quiet Transit.','Breaker Ledger traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(393,79,'Hallway Glow','quiet-transit-hollow-method-hallway-glow',3,239,'Hallway Glow is the preview focus from Quiet Transit.','Hallway Glow traces the emotional contour of quiet transit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(394,79,'Transfer Transit','quiet-transit-hollow-method-transfer-transit',4,268,'Transfer Transit is the preview focus from Quiet Transit.','Transfer Transit traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(395,79,'Rain Machine','quiet-transit-hollow-method-rain-machine',5,297,'Rain Machine is the preview focus from Quiet Transit.','Rain Machine traces the emotional contour of quiet transit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(396,80,'Transfer Machine','stone-circuit-hollow-method-transfer-machine',1,202,'Transfer Machine is the preview focus from Stone Circuit.','Transfer Machine traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(397,80,'Rain Murmur','stone-circuit-hollow-method-rain-murmur',2,231,'Rain Murmur is the preview focus from Stone Circuit.','Rain Murmur traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(398,80,'Invoice Light','stone-circuit-hollow-method-invoice-light',3,260,'Invoice Light is the preview focus from Stone Circuit.','Invoice Light traces the emotional contour of stone circuit in one sharp phrase.',1);
INSERT INTO "tracks" VALUES(399,80,'Current Note','stone-circuit-hollow-method-current-note',4,289,'Current Note is the preview focus from Stone Circuit.','Current Note traces the emotional contour of stone circuit in one sharp phrase.',0);
INSERT INTO "tracks" VALUES(400,80,'Median Line','stone-circuit-hollow-method-median-line',5,318,'Median Line is the preview focus from Stone Circuit.','Median Line traces the emotional contour of stone circuit in one sharp phrase.',0);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	bio TEXT, 
	city VARCHAR(80), 
	country VARCHAR(80), 
	address_line1 VARCHAR(200), 
	postal_code VARCHAR(30), 
	favorite_format VARCHAR(40), 
	favorite_scene_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(favorite_scene_id) REFERENCES scenes (id)
);
INSERT INTO "users" VALUES(1,'alice_j','alice.j@test.com','scrypt:32768:8:1$jattGpMscXJ483Xf$61fbe0ceaf7fa6442bc0964b55c2a96c633840b142719eca04af08ad55d34c75b083f18d92430185a587261b49b5fbd655cbc8c166d4512938d0a695213b6b52','Alice Johnson','Collects ambient and dub techno 12-inches.','Seattle','United States','128 Lake Union Ave','98109','vinyl',2,'2026-05-27 10:33:28.999466');
INSERT INTO "users" VALUES(2,'bob_c','bob.c@test.com','scrypt:32768:8:1$CKhedapqOu5J0hbN$9b89da1bc0d9b8e36ddb60b163448583047b86443f94b61d0b96a7201eed43b5d29901a0f38302ad78d6b12588016d6a055faaec345ddadbb316d2ac6f1c0f4a','Bob Chen','Hip-hop fan chasing sharp lyric sheets and live bootlegs.','Chicago','United States','77 Fulton Market','60607','digital',8,'2026-05-27 10:33:29.242393');
INSERT INTO "users" VALUES(3,'carol_d','carol.d@test.com','scrypt:32768:8:1$96ZrgZnFHeDAWyeY$17e84c179f7e0ba44cb6ac5b4cf86f90511cdc44a55619d31a88ea27e8a71b9397238f3eac0d0f29a681da8a063559664e758b23b9873c83c7442f16c3d8e82d','Carol Davis','Tags every purchase with the scene where she found it.','Brooklyn','United States','55 Bergen St','11201','cassette',3,'2026-05-27 10:33:29.477079');
INSERT INTO "users" VALUES(4,'david_k','david.k@test.com','scrypt:32768:8:1$KHZNQFtyEDiBWJ8u$cfcd45c55b82012b00b7e5b9355cfd4c81027fa20e1f691d67e049564f553c3aec0435591bcc4eb53d3091bc6ced979d256c7737b1f35b212b92d16ef5d35770','David Kim','Merch-heavy collector who buys a tote with almost every record.','Portland','United States','204 Burnside St','97209','shirt',6,'2026-05-27 10:33:29.722056');
CREATE TABLE wishlist_items (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	album_id INTEGER, 
	merch_item_id INTEGER, 
	added_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(album_id) REFERENCES albums (id), 
	FOREIGN KEY(merch_item_id) REFERENCES merch_items (id)
);
INSERT INTO "wishlist_items" VALUES(1,1,3,NULL,'2026-05-27 10:33:29.732420');
INSERT INTO "wishlist_items" VALUES(2,1,13,NULL,'2026-05-27 10:33:29.732921');
INSERT INTO "wishlist_items" VALUES(3,1,21,NULL,'2026-05-27 10:33:29.733260');
INSERT INTO "wishlist_items" VALUES(4,1,NULL,13,'2026-05-27 10:33:29.733576');
INSERT INTO "wishlist_items" VALUES(5,2,17,NULL,'2026-05-27 10:33:29.733903');
INSERT INTO "wishlist_items" VALUES(6,2,6,NULL,'2026-05-27 10:33:29.734219');
INSERT INTO "wishlist_items" VALUES(7,2,NULL,5,'2026-05-27 10:33:29.734545');
INSERT INTO "wishlist_items" VALUES(8,2,NULL,21,'2026-05-27 10:33:29.734848');
INSERT INTO "wishlist_items" VALUES(9,3,15,NULL,'2026-05-27 10:33:29.735187');
INSERT INTO "wishlist_items" VALUES(10,3,4,NULL,'2026-05-27 10:33:29.735541');
INSERT INTO "wishlist_items" VALUES(11,3,23,NULL,'2026-05-27 10:33:29.735848');
INSERT INTO "wishlist_items" VALUES(12,3,NULL,3,'2026-05-27 10:33:29.736139');
INSERT INTO "wishlist_items" VALUES(13,4,19,NULL,'2026-05-27 10:33:29.736441');
INSERT INTO "wishlist_items" VALUES(14,4,8,NULL,'2026-05-27 10:33:29.736766');
INSERT INTO "wishlist_items" VALUES(15,4,NULL,7,'2026-05-27 10:33:29.737082');
INSERT INTO "wishlist_items" VALUES(16,4,NULL,15,'2026-05-27 10:33:29.737901');
CREATE UNIQUE INDEX ix_genres_slug ON genres (slug);
CREATE UNIQUE INDEX ix_scenes_slug ON scenes (slug);
CREATE UNIQUE INDEX ix_labels_slug ON labels (slug);
CREATE UNIQUE INDEX ix_tags_slug ON tags (slug);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE UNIQUE INDEX ix_artists_slug ON artists (slug);
CREATE UNIQUE INDEX ix_albums_slug ON albums (slug);
CREATE UNIQUE INDEX ix_tracks_slug ON tracks (slug);
CREATE UNIQUE INDEX ix_merch_items_slug ON merch_items (slug);
COMMIT;
