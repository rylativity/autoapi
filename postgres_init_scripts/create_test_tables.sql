CREATE TABLE IF NOT EXISTS table1 (
    id SERIAL PRIMARY KEY,
    int_field INTEGER,
    string_field VARCHAR(255)
);
INSERT INTO table1 (int_field, string_field)
VALUES (1, 'abc'),
        (2, 'def'),
        (3, 'ghi');

CREATE TABLE IF NOT EXISTS table2 (
    id SERIAL PRIMARY KEY,
    bool_field BOOLEAN,
    string_field VARCHAR(255),
    double_field DOUBLE PRECISION
);
INSERT INTO table2 (bool_field, string_field, double_field)
VALUES (TRUE, 'abc', 0.12),
        (TRUE, 'def', 0.8),
        (FALSE, 'ghi', 3.14159265358);