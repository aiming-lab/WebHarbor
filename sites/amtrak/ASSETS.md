# Amtrak merged assets

The original contributor published `amtrak.tar.gz` at the immutable dataset
revision `lxr-max/WebHarbor@eac108f14be667b7e78972b0805d116ddea931d2`.
The reviewed archive SHA-256 is
`22f0132a5f9bfee45a641e8172050a94bb4fc0de4ad45f1d9e52deb50eb37f34`.
It has 308 validated managed members. Its SQLite seed SHA-256 is
`b245928c8b03741d17aa7c27f863a499e44034af607902cfa9c8d099c93591b4`.

The unchanged bundle is now merged into `ChilleD/WebHarbor` through
[HF PR #96](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/96),
at immutable revision `6f432484307f76ca3c58b1d5c8f7b614dfb34f54`.
Incomplete draft #30 was closed with a link to its replacement. All 44 existing
dataset files were preserved unchanged. No seed or image bytes changed.

`.assets-revision` pins this central merged revision and archive digest;
`scripts/fetch_assets.sh amtrak` verifies the digest before extraction.
Other sites retain their existing pins.

The seed's schedules/fares and generated SVG illustrations are deterministic
benchmark fixtures, not verified live Amtrak facts or source photographs.
