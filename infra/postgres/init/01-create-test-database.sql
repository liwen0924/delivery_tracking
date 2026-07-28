-- The API test suite runs against a real PostgreSQL. Giving it its own
-- database keeps `make test` from touching the demo data.
CREATE DATABASE tracker_test OWNER tracker;
