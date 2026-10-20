SELECT name FROM employee;
SELECT name FROM employees;
SELECT name FROM employees e JOIN departments d ON e.dept_id = d.id;
SELECT name FROM employees WHERE salary > 'abc';
SELECT id FROM employees WHERE age + 1;
SELECT x.name FROM employees e;
