-- 1. simple selection
SELECT name, salary FROM employees WHERE salary > 10000 ORDER BY salary DESC;

-- 2. JOIN with alias and compound condition
SELECT e.name, d.name AS department, e.salary * 12 AS yearly
FROM employees e JOIN departments d ON e.dept_id = d.id
WHERE d.city = 'Addis Ababa' AND e.age < 40
ORDER BY yearly DESC LIMIT 3;

-- 3. LEFT JOIN keeps employees without a department
SELECT e.name, d.name FROM employees e LEFT JOIN departments d ON e.dept_id = d.id;

-- 4. star + NOT/OR
SELECT * FROM departments WHERE NOT (city = 'Addis Ababa') OR id = 10;
