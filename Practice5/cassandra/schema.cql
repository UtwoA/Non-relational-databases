CREATE KEYSPACE IF NOT EXISTS job_market
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE job_market;

CREATE TABLE IF NOT EXISTS employers_by_id (
    employer_id uuid PRIMARY KEY,
    name text,
    industry text,
    website text,
    country text,
    city text,
    active boolean,
    created_at timestamp,
    updated_at timestamp
);

CREATE TABLE IF NOT EXISTS vacancies_by_id (
    vacancy_id uuid PRIMARY KEY,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    country text,
    region text,
    city text,
    remote boolean,
    employment_type text,
    experience_level text,
    salary_from int,
    salary_to int,
    currency text,
    posted_at timestamp,
    description text,
    skills set<text>,
    active boolean,
    updated_at timestamp
);

CREATE TABLE IF NOT EXISTS vacancies_feed (
    feed_name text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    country text,
    region text,
    city text,
    remote boolean,
    employment_type text,
    experience_level text,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((feed_name), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_employer (
    employer_id uuid,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    title text,
    profession text,
    country text,
    region text,
    city text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((employer_id), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_profession (
    profession text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    country text,
    region text,
    city text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((profession), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_region (
    country text,
    region text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    city text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((country, region), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_remote (
    remote boolean,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    country text,
    region text,
    city text,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((remote), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_employment_type (
    employment_type text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    country text,
    region text,
    city text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((employment_type), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_experience_level (
    experience_level text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    country text,
    region text,
    city text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((experience_level), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS vacancies_by_city (
    country text,
    city text,
    posted_date date,
    posted_at timestamp,
    vacancy_id uuid,
    employer_id uuid,
    employer_name text,
    title text,
    profession text,
    region text,
    remote boolean,
    salary_from int,
    salary_to int,
    currency text,
    active boolean,
    PRIMARY KEY ((country, city), posted_date, posted_at, vacancy_id)
) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC);

CREATE TABLE IF NOT EXISTS region_stats_by_key (
    country text,
    region text,
    posted_date date,
    vacancy_count int,
    average_salary_from double,
    average_salary_to double,
    remote_count int,
    active_count int,
    updated_at timestamp,
    PRIMARY KEY ((country, region), posted_date)
) WITH CLUSTERING ORDER BY (posted_date DESC);
