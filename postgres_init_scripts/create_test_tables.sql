CREATE TABLE test (
    id SERIAL PRIMARY KEY,
    int_field INTEGER,
    string_field VARCHAR(255)
);
INSERT INTO test (int_field, string_field)
VALUES (1, 'abc'),
        (2, 'def'),
        (3, 'ghi');