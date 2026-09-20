# Rollout approval record

Draft creation and review are implemented behind dark-launch flags. Activation,
registration workers, and remote provider start remain disabled by default.
The PostgreSQL/workspace identity gate is still blocked by legacy nullable
ownership and global keys, so no production cutover approval is recorded. An
operator may enable flags only after the prerequisite evidence is updated and
the responsible owner records approval here.
