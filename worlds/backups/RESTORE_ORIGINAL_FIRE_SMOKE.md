# Restore the original apron fire and smoke appearance

The untouched world backup is `earthquake_landslide_apron_world.before_fire_effects_20261029.sdf`.
The original static `fire_only` and `smoke_only` model folders are in `original_fire_smoke_models/`.

From the Drone-Swarm project root, restore both the original world and the model assets with:

```bash
cp worlds/backups/earthquake_landslide_apron_world.before_fire_effects_20261029.sdf worlds/earthquake_landslide_apron_world.sdf
cp -a worlds/backups/original_fire_smoke_models/fire_only/. worlds/disaster_assets/models/fire_only/
cp -a worlds/backups/original_fire_smoke_models/smoke_only/. worlds/disaster_assets/models/smoke_only/
```

Then run `./integration/mavsdk_controller/launch_three_px4.sh` to launch the restored environment.
