from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.environ.get("RUN_PGBOUNCER_RUNTIME_TESTS") == "1",
    "Set RUN_PGBOUNCER_RUNTIME_TESTS=1 to run the live pool saturation drill",
)
class PgBouncerRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            ["docker", "compose", "up", "-d", "postgres", "pgbouncer"],
            cwd=ROOT,
            check=True,
        )

    def test_twenty_four_clients_share_a_bounded_server_pool(self) -> None:
        script = r'''
set -eu
echo "TARGET_DB=$HEALTH_DB"
for index in $(seq 1 24); do
  PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 6432 -U "$DB_USER" -d "$HEALTH_DB" \
    -v ON_ERROR_STOP=1 -c "BEGIN; SELECT pg_sleep(5); COMMIT;" >/dev/null &
done
sleep 1
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 6432 -U "$DB_USER" -d pgbouncer \
  -At -F '|' -c "SHOW POOLS;"
wait
'''
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "pgbouncer", "sh", "-lc", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target_database = next(
            line.removeprefix("TARGET_DB=")
            for line in result.stdout.splitlines()
            if line.startswith("TARGET_DB=")
        )
        rows = [line.split("|") for line in result.stdout.splitlines() if "|" in line]
        application = next(row for row in rows if row[0] == target_database)
        client_count = int(application[2]) + int(application[3])
        server_count = int(application[6]) + int(application[9])
        self.assertGreaterEqual(client_count, 24)
        self.assertLessEqual(server_count, 20)


if __name__ == "__main__":
    unittest.main()
