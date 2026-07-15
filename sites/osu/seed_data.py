#!/usr/bin/env python3
"""Seed all Ohio State University mirror data. Idempotent."""
from datetime import datetime, timedelta


def seed():
    """Seed all data. Gated on College.query.first() to be idempotent."""
    from app import (db, College, Department, Program, NewsArticle, Event,
                     ResearchCenter, Faculty, AthleticTeam, User, slugify)

    if College.query.first():
        return

    # ── Helper ────────────────────────────────────────────────────────────────
    def _slug(text, extra=''):
        base = slugify(text)
        if extra:
            base = base + '-' + slugify(extra)
        return base

    # ─────────────────────────────────────────────────────────────────────────
    # COLLEGES
    # ─────────────────────────────────────────────────────────────────────────
    college_data = [
        ('Arts and Sciences', 'Dean Patricia Bauer', 1870, 12000, 4000,
         'The College of Arts and Sciences is the intellectual and academic heart of Ohio State. '
         'It offers over 80 majors and 200 graduate programs spanning the humanities, social sciences, '
         'natural sciences, and mathematics. The college is home to more than 1,400 faculty and serves '
         'roughly 16,000 undergraduate and graduate students.'),
        ('Fisher College of Business', 'Dean Anil Makhija', 1916, 4500, 1800,
         'Fisher College of Business at Ohio State is consistently ranked among the nation\'s top '
         'business schools. Fisher offers undergraduate, MBA, specialized master\'s, and doctoral '
         'programs that prepare students for leadership in a globally connected marketplace.'),
        ('Education and Human Ecology', 'Dean Carey Andrzejewski', 1895, 1800, 1200,
         'The College of Education and Human Ecology prepares leaders in education, human development, '
         'family science, and nutrition. EHE faculty conduct research that improves lives at the '
         'individual, family, community, and policy levels.'),
        ('Engineering', 'Dean Ayanna Howard', 1870, 8000, 4500,
         'The College of Engineering at Ohio State is one of the largest and most comprehensive '
         'engineering colleges in the United States. With 26 departments and research centers, '
         'it drives economic growth and technological innovation across Ohio and beyond.'),
        ('Food, Agricultural, and Environmental Sciences', 'Dean Cathann Kress', 1870, 3200, 1200,
         'CFAES advances knowledge at the intersection of agriculture, food, environment, and human '
         'health. The college operates the Ohio Agricultural Research and Development Center and '
         'the OSU Extension system across all 88 Ohio counties.'),
        ('Moritz College of Law', 'Dean Wendy Smooth', 1891, 0, 650,
         'Moritz College of Law is one of the nation\'s leading law schools, offering the JD degree '
         'and several specialized graduate programs. The college is known for its commitment to public '
         'service, hands-on clinical education, and cutting-edge legal scholarship.'),
        ('Medicine', 'Dean K. Craig Kent', 1914, 0, 900,
         'The Ohio State University College of Medicine is one of the largest medical schools in '
         'the United States. Affiliated with the Wexner Medical Center and the James Cancer Hospital, '
         'it is a national leader in medical education, research, and patient care.'),
        ('Nursing', 'Dean Bernadette Melnyk', 1914, 600, 400,
         'The College of Nursing advances nursing science and prepares professional nurses for '
         'leadership roles in health care. It offers BSN, MS, DNP, and PhD programs and is known '
         'for its focus on wellness, evidence-based practice, and mental health.'),
        ('Optometry', 'Dean Karla Zadnik', 1914, 200, 250,
         'The College of Optometry is recognized as one of the finest optometric colleges in the '
         'world. It offers a four-year OD degree program and conducts pioneering research in '
         'myopia, glaucoma, and vision rehabilitation.'),
        ('Pharmacy', 'Dean Henry Mann', 1885, 300, 350,
         'The College of Pharmacy prepares pharmacists and pharmaceutical scientists to improve '
         'medication therapy outcomes. Its PharmD program integrates cutting-edge research with '
         'experiential learning at leading clinical sites across Ohio.'),
        ('Public Health', 'Dean Amy Ferketich', 2012, 0, 600,
         'The College of Public Health educates future leaders committed to improving the health '
         'of communities locally, nationally, and globally. Degree programs in epidemiology, health '
         'behavior, environmental health, and health services management prepare graduates for '
         'impact in government, industry, and research.'),
        ('Social Work', 'Dean Tom Gregoire', 1914, 300, 500,
         'The College of Social Work is dedicated to advancing social and economic justice and '
         'improving quality of life for people across the lifespan. Programs emphasize field '
         'practice, evidence-based interventions, and policy advocacy.'),
        ('Veterinary Medicine', 'Dean Rustin Moore', 1885, 400, 500,
         'The College of Veterinary Medicine is consistently ranked among the top vet schools in '
         'the nation. Its teaching hospital serves tens of thousands of animal patients each year, '
         'and its researchers pioneer breakthroughs in both animal and human health.'),
        ('John Glenn College of Public Affairs', 'Dean Trevor Brown', 1999, 100, 350,
         'The John Glenn College of Public Affairs trains the next generation of public servants, '
         'policy analysts, and nonprofit leaders. Named for the legendary Ohio astronaut and U.S. '
         'Senator, the college emphasizes ethics, analytical rigor, and civic engagement.'),
        ('Dentistry', 'Dean Kristin Williams', 1890, 0, 400,
         'The College of Dentistry provides comprehensive oral health care and trains outstanding '
         'dental professionals. Its clinic serves tens of thousands of patients annually, and its '
         'researchers advance knowledge in oral biology, dental materials, and community oral health.'),
        ('Graduate School', 'Dean Sean Carson', 1878, 0, 14000,
         'The Graduate School oversees graduate education across all disciplines at Ohio State. '
         'It supports master\'s, doctoral, and professional degree programs and fosters the '
         'interdisciplinary research enterprise of the university.'),
    ]

    colleges = {}
    for name, dean, founded, ug, gr, desc in college_data:
        c = College(
            name=name,
            slug=slugify(name),
            dean=dean,
            founded_year=founded,
            undergrad_count=ug,
            grad_count=gr,
            description=desc,
        )
        db.session.add(c)
        colleges[name] = c
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # DEPARTMENTS
    # ─────────────────────────────────────────────────────────────────────────
    dept_data = [
        # Arts and Sciences
        ('Department of Mathematics', 'Arts and Sciences', 'Dr. James Cogdell',
         '(614) 292-4975', '100 Mathematics Building',
         'Mathematics at Ohio State encompasses research in algebra, analysis, geometry, '
         'topology, logic, and applied mathematics. The department houses internationally '
         'recognized faculty and produces PhD graduates who lead academia and industry.'),
        ('Department of Physics', 'Arts and Sciences', 'Dr. Richard Furnstahl',
         '(614) 292-5713', '174 W. 18th Avenue',
         'Physics research at Ohio State spans particle physics, condensed matter, biophysics, '
         'and astrophysics. The department operates state-of-the-art experimental facilities '
         'and has strong ties to national laboratories.'),
        ('Department of Chemistry and Biochemistry', 'Arts and Sciences', 'Dr. Claudia Turro',
         '(614) 292-2133', '100 W. 18th Avenue',
         'Chemistry and Biochemistry at Ohio State integrates teaching and research across '
         'organic, inorganic, physical, analytical, and biological chemistry subfields.'),
        ('Department of Computer Science and Engineering', 'Engineering', 'Dr. Srinivasan Parthasarathy',
         '(614) 292-5813', '395 Dreese Lab',
         'CSE at Ohio State is at the forefront of computing research in machine learning, '
         'security, systems, theory, and human-computer interaction. The department collaborates '
         'with industry partners and national labs.'),
        ('Department of Electrical and Computer Engineering', 'Engineering', 'Dr. Joel Johnson',
         '(614) 292-3005', '205 Dreese Lab',
         'ECE research spans signal processing, electromagnetics, VLSI design, power systems, '
         'and wireless communications. The department has strong industry partnerships and '
         'state-of-the-art laboratories.'),
        ('Department of Mechanical and Aerospace Engineering', 'Engineering', 'Dr. Marcelo Dapino',
         '(614) 292-2288', '201 W. 19th Avenue',
         'MAE covers thermodynamics, fluid mechanics, solid mechanics, dynamics, robotics, '
         'and aerospace systems. The department houses research centers including the Center '
         'for Automotive Research.'),
        ('Department of Economics', 'Arts and Sciences', 'Dr. Bruce Weinberg',
         '(614) 292-0552', '1945 N. High Street',
         'The Department of Economics provides rigorous training in microeconomics, '
         'macroeconomics, econometrics, and applied economics. Research spans labor, health, '
         'development, public finance, and international economics.'),
        ('Department of Psychology', 'Arts and Sciences', 'Dr. Steven Hecht',
         '(614) 292-1739', '1835 Neil Avenue Mall',
         'Psychology at Ohio State integrates research and training in clinical, cognitive, '
         'developmental, neuroscience, quantitative, and social psychology.'),
        ('Department of History', 'Arts and Sciences', 'Dr. Stephanie Smith',
         '(614) 292-2674', '104 Dulles Hall',
         'The History Department offers programs spanning American, European, African, Asian, '
         'and world history. Faculty conduct research on topics from medieval Europe to '
         'contemporary America.'),
        ('Department of English', 'Arts and Sciences', 'Dr. Robyn Warhol',
         '(614) 292-6065', '164 W. 17th Avenue',
         'English at Ohio State encompasses literary studies, creative writing, rhetoric and '
         'composition, linguistics, and cultural studies. The department has a distinguished '
         'tradition of interdisciplinary scholarship.'),
        ('Department of Finance', 'Fisher College of Business', 'Dr. Kewei Hou',
         '(614) 292-9470', '700 Fisher Hall',
         'Finance at Fisher prepares students for careers in investment banking, asset management, '
         'corporate finance, and financial research. Research focuses on asset pricing, '
         'corporate governance, and financial markets.'),
        ('Department of Management and Human Resources', 'Fisher College of Business', 'Dr. David Greenberger',
         '(614) 292-2311', '700 Fisher Hall',
         'The MHR department addresses critical topics in organizational behavior, human resource '
         'management, leadership, and strategic management through rigorous research and '
         'experiential learning.'),
        ('Department of Biomedical Informatics', 'Medicine', 'Dr. Philip Payne',
         '(614) 293-3600', '1800 Cannon Drive',
         'Biomedical Informatics bridges medicine, nursing, pharmacy, and computing to advance '
         'health data science and clinical decision support. Faculty lead research in clinical '
         'natural language processing, patient safety, and precision medicine.'),
        ('Department of Epidemiology', 'Public Health', 'Dr. Amy Ferketich',
         '(614) 292-0745', '1841 Neil Avenue',
         'Epidemiology faculty study the distribution and determinants of health and disease '
         'in populations. Specialty areas include cancer, cardiovascular disease, infectious '
         'disease, reproductive health, and social epidemiology.'),
        ('Department of Environmental Engineering', 'Engineering', 'Dr. Linda Weavers',
         '(614) 292-2006', '470 Hitchcock Hall',
         'Environmental Engineering addresses water, air, and soil quality challenges using '
         'science and engineering principles. Research spans water treatment, remediation, '
         'and sustainable infrastructure design.'),
    ]

    departments = {}
    for name, college_name, chair, phone, loc, desc in dept_data:
        d = Department(
            name=name,
            slug=slugify(name),
            college_id=colleges[college_name].id,
            chair=chair,
            phone=phone,
            location=loc,
            description=desc,
        )
        db.session.add(d)
        departments[name] = d
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRAMS
    # ─────────────────────────────────────────────────────────────────────────
    program_data = [
        # Undergrad BS/BA
        ('Bachelor of Arts in Mathematics', 'BA', 'Arts and Sciences', 'Department of Mathematics',
         120, 4.0, 'December 1', False, False,
         'The BA in Mathematics provides students with a strong foundation in mathematical '
         'reasoning and problem-solving. Students take courses in calculus, linear algebra, '
         'abstract algebra, real analysis, and elective courses in their area of interest.',
         'Calculus sequence; Linear Algebra; Abstract Algebra; Real Analysis; 3 electives in pure or applied math.'),
        ('Bachelor of Science in Computer Science and Engineering', 'BS', 'Engineering', 'Department of Computer Science and Engineering',
         130, 4.0, 'February 1', False, False,
         'The BS in CSE prepares students for careers in software engineering, systems design, '
         'machine learning, and computer science research. The curriculum covers algorithms, '
         'data structures, operating systems, computer architecture, and specialized electives.',
         'Calculus sequence; Physics; Programming fundamentals; Data Structures; Algorithms; OS; Compilers; Senior capstone.'),
        ('Bachelor of Science in Mechanical Engineering', 'BS', 'Engineering', 'Department of Mechanical and Aerospace Engineering',
         132, 4.0, 'February 1', False, False,
         'The BS in Mechanical Engineering at Ohio State covers thermodynamics, fluid dynamics, '
         'solid mechanics, dynamics, and machine design. Students gain hands-on experience in '
         'state-of-the-art laboratories and design projects.',
         'Calculus; Physics; Engineering mechanics; Thermodynamics; Fluid mechanics; Materials science; Design capstone.'),
        ('Bachelor of Science in Economics', 'BS', 'Arts and Sciences', 'Department of Economics',
         122, 4.0, 'February 1', False, False,
         'The BS in Economics offers rigorous training in economic theory, quantitative methods, '
         'and applied economics. Graduates pursue careers in consulting, finance, government, '
         'and economics research.',
         'Micro and macroeconomic theory; Econometrics; Math for economists; 5 field electives.'),
        ('Bachelor of Arts in English', 'BA', 'Arts and Sciences', 'Department of English',
         120, 4.0, 'February 1', False, False,
         'The BA in English develops critical reading, research, and writing skills through the '
         'study of literature, rhetoric, creative writing, and linguistics. Graduates succeed '
         'in law, business, journalism, education, and many other fields.',
         'Foundations in literary study; Writing seminars; Literature survey courses; Upper-level seminars; Capstone.'),
        ('Bachelor of Science in Physics', 'BS', 'Arts and Sciences', 'Department of Physics',
         130, 4.0, 'February 1', False, False,
         'The BS in Physics provides rigorous preparation in classical and modern physics, '
         'mathematical methods, and experimental techniques. Students develop skills for '
         'careers in research, engineering, education, and technology.',
         'Calculus-based physics sequence; Math methods; Quantum mechanics; E&M; Thermodynamics; Advanced lab; Capstone.'),
        ('Bachelor of Science in Business Administration', 'BS', 'Fisher College of Business', 'Department of Finance',
         121, 4.0, 'December 1', False, False,
         'The BSBA at Fisher prepares students for leadership in diverse business environments. '
         'Specializations include finance, marketing, management, supply chain, and information systems.',
         'Business core; Accounting; Statistics; Management; Finance; Marketing; Operations; Specialization courses; Capstone.'),
        # Graduate
        ('Master of Science in Computer Science', 'MS', 'Engineering', 'Department of Computer Science and Engineering',
         30, 2.0, 'December 15', False, False,
         'The MS in CSE at Ohio State offers depth in computer science theory and applications. '
         'Students choose from thesis and non-thesis options and specialize in areas including '
         'machine learning, systems, security, or algorithms.',
         'Core graduate CS courses; Thesis or project; 10 credit hours of electives.'),
        ('Master of Science in Electrical and Computer Engineering', 'MS', 'Engineering', 'Department of Electrical and Computer Engineering',
         30, 2.0, 'January 15', False, True,
         'The MS in ECE prepares engineers for advanced work in signal processing, communications, '
         'VLSI, power systems, and more. Both thesis and non-thesis options available.',
         'Graduate core courses; Electives; Thesis or final project.'),
        ('Master of Business Administration', 'MBA', 'Fisher College of Business', 'Department of Management and Human Resources',
         60, 2.0, 'April 1', False, False,
         'The Fisher MBA develops business leaders through a rigorous curriculum combining '
         'management fundamentals with real-world application. Specializations available in '
         'finance, marketing, entrepreneurship, and operations.',
         'Business core; Leadership skills; Industry-specific electives; Business simulation; Capstone project.'),
        ('Doctor of Philosophy in Mathematics', 'PhD', 'Arts and Sciences', 'Department of Mathematics',
         80, 5.0, 'January 1', False, True,
         'The PhD in Mathematics at Ohio State is a research-intensive program that prepares '
         'students for academic and research careers. Students specialize in algebra, analysis, '
         'geometry, topology, logic, or applied mathematics.',
         'Graduate coursework; Qualifying exams; Dissertation; Teaching duties.'),
        ('Doctor of Philosophy in Physics', 'PhD', 'Arts and Sciences', 'Department of Physics',
         80, 5.5, 'December 1', False, True,
         'The PhD in Physics prepares students for careers in academic research, national '
         'laboratories, and industry. Students conduct original research in particle physics, '
         'condensed matter, biophysics, or astrophysics.',
         'Coursework; Qualifying exam; Research rotations; Dissertation.'),
        ('Doctor of Philosophy in Computer Science', 'PhD', 'Engineering', 'Department of Computer Science and Engineering',
         80, 5.0, 'December 1', False, True,
         'The PhD in CS at Ohio State is a research-intensive program with national recognition '
         'in machine learning, security, theoretical computer science, and human-computer '
         'interaction. Students publish in top venues and collaborate with industry.',
         'Coursework; Candidacy exam; Research; Dissertation; Publications.'),
        ('Juris Doctor', 'JD', 'Moritz College of Law', None,
         90, 3.0, 'April 1', False, False,
         'The JD at Moritz College of Law prepares students for practice in any legal field. '
         'Known for experiential learning, the program offers more than 20 clinics, mock trial '
         'competitions, and strong placement in law firms, government, and public service.',
         'Legal writing and research; Constitutional law; Contracts; Torts; Civil procedure; Professional responsibility; Electives; Clinical experience.'),
        ('Doctor of Medicine', 'MD', 'Medicine', 'Department of Biomedical Informatics',
         0, 4.0, 'October 15', False, False,
         'The MD program at Ohio State College of Medicine offers exceptional training through '
         'the unique Buckeye Transformative Education in Medicine curriculum. Students benefit '
         'from early clinical experiences, research opportunities, and connections to the '
         'nationally ranked Wexner Medical Center.',
         'Pre-clinical foundations; Clinical rotations; Research; Residency preparation.'),
        ('Doctor of Pharmacy', 'PharmD', 'Pharmacy', None,
         0, 4.0, 'November 1', False, False,
         'The PharmD at Ohio State prepares pharmacists for clinical, research, and industry '
         'careers. The curriculum integrates pharmaceutical sciences with patient-centered care '
         'through experiential learning at outstanding clinical sites.',
         'Pharmaceutical sciences; Pharmacotherapy; Clinical rotations; Advanced practice experiences.'),
        ('Doctor of Veterinary Medicine', 'DVM', 'Veterinary Medicine', None,
         0, 4.0, 'October 1', False, False,
         'The DVM program at Ohio State is consistently ranked among the top in the nation. '
         'Students train at the Veterinary Medical Center, one of the nation\'s premier '
         'veterinary teaching hospitals, and benefit from research opportunities across '
         'all animal species.',
         'Biomedical sciences; Clinical sciences; Rotations; Research elective.'),
        ('Doctor of Optometry', 'OD', 'Optometry', None,
         0, 4.0, 'October 1', False, False,
         'The OD program at Ohio State prepares optometrists for comprehensive patient care '
         'in primary care, specialty, and research settings. Students gain extensive clinical '
         'experience at the OSU Eye Center and affiliated sites.',
         'Optometric sciences; Clinical methods; Patient care rotations; Research.'),
        ('Master of Public Health', 'MPH', 'Public Health', 'Department of Epidemiology',
         48, 2.0, 'February 1', True, False,
         'The MPH at Ohio State prepares public health professionals to assess, plan, and '
         'implement programs that improve community health. Concentrations include epidemiology, '
         'health behavior, environmental health, and health management.',
         'Core public health competencies; Concentration courses; Practicum; Capstone project.'),
        ('Master of Science in Environmental Engineering', 'MS', 'Engineering', 'Department of Environmental Engineering',
         30, 2.0, 'January 15', False, False,
         'The MS in Environmental Engineering addresses water and wastewater treatment, '
         'air quality, solid waste management, and environmental remediation. Both thesis '
         'and non-thesis options are available.',
         'Graduate core; Electives; Thesis or project; Professional seminar.'),
    ]

    for (name, deg, college_name, dept_name, units, dur, deadline,
         is_online, gre, desc, reqs) in program_data:
        college_obj = colleges.get(college_name)
        dept_obj = departments.get(dept_name) if dept_name else None
        slug = slugify(name) + '-' + deg.lower()
        p = Program(
            name=name,
            slug=slug,
            degree_type=deg,
            college_id=college_obj.id if college_obj else None,
            department_id=dept_obj.id if dept_obj else None,
            units=units,
            duration_years=dur,
            application_deadline=deadline,
            is_online=is_online,
            gre_required=gre,
            description=desc,
            requirements=reqs,
        )
        db.session.add(p)
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # RESEARCH CENTERS
    # ─────────────────────────────────────────────────────────────────────────
    base_year = datetime(2024, 1, 1)
    research_data = [
        ('Translational Data Analytics Institute', 'TDAI', 'Dr. Beth Plale',
         'Arts and Sciences', 2016,
         'Data analytics, Machine learning, Health informatics, Social science',
         'https://tdai.osu.edu',
         'TDAI brings together faculty from across Ohio State to harness the power of data analytics '
         'to address complex problems in society. The institute supports interdisciplinary research '
         'in health, agriculture, smart cities, and social sciences.'),
        ('Byrd Alzheimer\'s Center and Research Institute', 'Byrd', 'Dr. Douglas Scharre',
         'Medicine', 1987,
         'Alzheimer\'s disease, Dementia, Neuroimaging, Clinical trials',
         '',
         'The Byrd Alzheimer\'s Center is dedicated to discovering causes and cures for Alzheimer\'s '
         'disease and related dementias. Researchers conduct clinical trials and basic science studies '
         'to advance diagnosis, prevention, and treatment.'),
        ('Infectious Disease Institute', 'IDI', 'Dr. Michael Oglesbee',
         'Veterinary Medicine', 2008,
         'Infectious disease, Epidemiology, One Health, Vaccines',
         'https://idi.osu.edu',
         'IDI brings together virologists, bacteriologists, immunologists, and epidemiologists to '
         'address infectious disease threats to humans, animals, and ecosystems through the One Health '
         'approach. Research programs span HIV, influenza, SARS-CoV-2, and emerging pathogens.'),
        ('Ohio Supercomputer Center', 'OSC', 'Dr. David Bickel',
         'Engineering', 1987,
         'High-performance computing, Scientific computing, Data storage, Visualization',
         'https://www.osc.edu',
         'The Ohio Supercomputer Center is a statewide resource supporting computational research '
         'at Ohio State and institutions across Ohio. OSC provides high-performance computing, '
         'data storage, and training to researchers in science, engineering, and the humanities.'),
        ('Center for Automotive Research', 'CAR', 'Dr. Giorgio Rizzoni',
         'Engineering', 1991,
         'Electric vehicles, Autonomous driving, Energy storage, Powertrain systems',
         'https://car.osu.edu',
         'CAR partners with automotive industry leaders to advance electrification, autonomy, '
         'connectivity, and mobility. Research programs address battery systems, vehicle dynamics, '
         'driver behavior, and sustainable transportation systems.'),
        ('Battelle Center for Science, Engineering and Public Policy', 'Battelle', 'Dr. Clay Johnston',
         'John Glenn College of Public Affairs', 2010,
         'Science policy, Technology policy, Energy policy, Climate policy',
         '',
         'The Battelle Center examines how science and technology shape public policy choices. '
         'Faculty and students analyze energy, environment, health, and security policy, '
         'bridging the gap between scientific evidence and policy action.'),
        ('James Cancer Hospital and Solove Research Institute', 'James', 'Dr. William Farrar',
         'Medicine', 1990,
         'Cancer research, Oncology, Clinical trials, Precision medicine',
         'https://cancer.osu.edu',
         'The James Cancer Hospital and Solove Research Institute is Ohio\'s only comprehensive '
         'cancer center and ranks among the nation\'s top cancer programs. Researchers develop '
         'novel immunotherapies, targeted treatments, and early detection methods.'),
        ('Wexner Medical Center', 'WMC', 'Dr. Hal Paz',
         'Medicine', 1952,
         'Clinical medicine, Medical education, Translational research, Health systems',
         'https://wexnermedical.osu.edu',
         'The Ohio State Wexner Medical Center is a nationally recognized academic medical center '
         'with hospitals, clinical programs, and research institutes advancing human health. '
         'Researchers translate scientific discoveries into new diagnostics and therapies.'),
        ('Drug Enforcement and Policy Center', 'DEPC', 'Dr. Douglas Berman',
         'Moritz College of Law', 2018,
         'Drug policy, Criminal justice, Marijuana policy, Opioid epidemic',
         'https://depc.osu.edu',
         'DEPC is the leading academic center on drug law and policy, examining enforcement, '
         'regulation, and reform. Center experts provide evidence-based analysis on topics '
         'including the opioid crisis, marijuana legalization, and sentencing reform.'),
        ('Center for Clean Hydrogen', 'CCH', 'Dr. Yann Guezennec',
         'Engineering', 2022,
         'Hydrogen energy, Fuel cells, Green hydrogen, Energy storage',
         '',
         'The Center for Clean Hydrogen advances science and engineering to enable a hydrogen '
         'economy. Research addresses hydrogen production, storage, transportation, and fuel '
         'cell technology for transportation and power generation applications.'),
        ('Advanced Computing Center for the Arts and Design', 'ACCAD', 'Dr. Maria Palazzi',
         'Arts and Sciences', 1987,
         'Digital arts, Computer animation, Visualization, Motion capture',
         'https://accad.osu.edu',
         'ACCAD is an internationally recognized center for research and practice at the '
         'intersection of art, design, and computing. Faculty and students develop new forms '
         'of digital art, animation, interactive media, and scientific visualization.'),
        ('Center for Cognitive and Brain Sciences', 'CCBS', 'Dr. Michael DeSchutter',
         'Arts and Sciences', 2007,
         'Neuroscience, Cognitive science, Decision making, Language',
         '',
         'CCBS is an interdisciplinary research center addressing fundamental questions about '
         'the brain and mind. Research programs span perception, attention, memory, decision '
         'making, language, and social cognition using behavioral, neuroimaging, and computational methods.'),
        ('Sustainability Institute', 'SI', 'Dr. Julie Newman',
         'Food, Agricultural, and Environmental Sciences', 2008,
         'Sustainability, Climate change, Campus operations, Environmental policy',
         'https://si.osu.edu',
         'The Sustainability Institute leads Ohio State\'s efforts to advance sustainability '
         'in research, education, and campus operations. The institute supports interdisciplinary '
         'research on energy, water, food systems, biodiversity, and climate resilience.'),
        ('Chadwick Arboretum and Learning Gardens', 'Chadwick', 'Dr. Susan Pell',
         'Food, Agricultural, and Environmental Sciences', 1980,
         'Plant science, Horticulture, Biodiversity, Sustainable landscapes',
         'https://chadwickarboretum.osu.edu',
         'Chadwick Arboretum is a 60-acre living laboratory on the Columbus campus featuring '
         'thousands of plant species. The arboretum supports research in plant science, '
         'sustainable horticulture, and environmental education for the community.'),
        ('Center for Biostatistics', 'CBS', 'Dr. Michael Pennell',
         'Public Health', 2001,
         'Biostatistics, Clinical trials, Epidemiology, Statistical genetics',
         '',
         'The Center for Biostatistics provides statistical expertise and methodology development '
         'to support clinical and public health research across Ohio State. Faculty collaborate '
         'on clinical trials, cohort studies, and genomic data analysis.'),
    ]

    rc_map = {}
    for (name, short, director, college_name, founded, focus, url, desc) in research_data:
        rc = ResearchCenter(
            name=name,
            slug=slugify(name),
            director=director,
            college_id=colleges.get(college_name, colleges['Arts and Sciences']).id,
            founded_year=founded,
            focus_areas=focus,
            url=url,
            description=desc,
        )
        db.session.add(rc)
        rc_map[name] = rc
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # FACULTY
    # ─────────────────────────────────────────────────────────────────────────
    faculty_data = [
        ('Dr. James Cogdell', 'Professor', 'Department of Mathematics', 'cogdell.1@osu.edu', 'MW 724', '(614) 292-4975',
         'Number theory, Automorphic forms, L-functions, Langlands program',
         'Professor Cogdell is a leading number theorist specializing in automorphic forms and the Langlands program. '
         'He has received numerous awards and fellowships for his research contributions.', False),
        ('Dr. Claudia Turro', 'Professor and Chair', 'Department of Chemistry and Biochemistry', 'turro.1@osu.edu', 'Evans 100D', '(614) 292-6567',
         'Inorganic photochemistry, Solar energy conversion, Anticancer agents, Ruthenium complexes',
         'Professor Turro leads research in inorganic photochemistry with applications in solar energy and cancer therapy. '
         'Her group develops ruthenium-based complexes for photoactivated cancer treatment.', False),
        ('Dr. Richard Furnstahl', 'Professor', 'Department of Physics', 'furnstahl.1@osu.edu', 'M2048 Physics Research Building', '(614) 292-4830',
         'Nuclear physics, Quantum chromodynamics, Effective field theory, Machine learning in physics',
         'Professor Furnstahl is a nuclear theorist who uses effective field theory and Bayesian methods '
         'to study nuclear structure and reactions.', False),
        ('Dr. Srinivasan Parthasarathy', 'Professor and Chair', 'Department of Computer Science and Engineering', 'parthasarathy.2@osu.edu', '591 Dreese Lab', '(614) 292-2568',
         'Data mining, Machine learning, Graph mining, Bioinformatics',
         'Professor Parthasarathy is an internationally recognized expert in data mining, machine learning, '
         'and graph analytics. His group develops algorithms for large-scale data analysis with applications '
         'in health care, social networks, and genomics.', False),
        ('Dr. Marcelo Dapino', 'Professor and Honda R&D Americas Chair', 'Department of Mechanical and Aerospace Engineering', 'dapino.1@osu.edu', '201 W. 19th Avenue', '(614) 292-9138',
         'Smart materials, Vibration control, Automotive engineering, Magnetostrictive actuators',
         'Professor Dapino is a leading researcher in smart materials and structural acoustics, '
         'with applications in automotive NVH and adaptive structures.', False),
        ('Dr. Bruce Weinberg', 'Professor', 'Department of Economics', 'weinberg.27@osu.edu', '422 Arps Hall', '(614) 292-0553',
         'Labor economics, Innovation, Science of science, Health economics',
         'Professor Weinberg studies the economics of innovation, labor markets, and health. '
         'His research on the relationship between age and scientific productivity has received '
         'wide attention in academia and the popular press.', False),
        ('Dr. Philip Payne', 'Professor and Chair', 'Department of Biomedical Informatics', 'payne.38@osu.edu', '1800 Cannon Drive', '(614) 293-3600',
         'Biomedical informatics, Clinical NLP, Precision medicine, Learning health systems',
         'Professor Payne leads the Department of Biomedical Informatics and is a pioneer in '
         'data-driven approaches to clinical decision support and precision medicine.', False),
        ('Dr. Amy Ferketich', 'Professor and Dean', 'Department of Epidemiology', 'ferketich.1@osu.edu', '250 Cunz Hall', '(614) 292-0745',
         'Tobacco control, Cancer epidemiology, Health disparities, Behavioral interventions',
         'Dean Ferketich is a nationally recognized tobacco control researcher who has led '
         'population-based studies on smoking cessation, tobacco marketing, and health disparities.', False),
        ('Dr. David Greenberger', 'Professor Emeritus', 'Department of Management and Human Resources', 'greenberger.1@osu.edu', '700 Fisher Hall', '(614) 292-0040',
         'Organizational behavior, Leadership, Work and family, Entrepreneurship',
         'Professor Greenberger is a pioneer in organizational behavior research and has made '
         'foundational contributions to our understanding of leadership and organizational control.', True),
        ('Dr. Kewei Hou', 'Professor', 'Department of Finance', 'hou.28@osu.edu', '750 Fisher Hall', '(614) 292-0552',
         'Asset pricing, Empirical finance, Factor models, Market anomalies',
         'Professor Hou is one of the leading empirical finance researchers of his generation, '
         'known for the q-factor model of stock returns and research on market anomalies.', False),
        ('Dr. Douglas Scharre', 'Professor and Director', 'Department of Epidemiology', 'scharre.1@osu.edu', '395 W. 12th Avenue', '(614) 293-4969',
         'Alzheimer\'s disease, Cognitive assessment, Dementia treatment, Brain aging',
         'Professor Scharre directs the Division of Cognitive Neurology and the Byrd Alzheimer\'s Center. '
         'He developed the widely used Self-Administered Gerocognitive Exam (SAGE) for early '
         'detection of cognitive impairment.', False),
        ('Dr. Giorgio Rizzoni', 'Professor and Director', 'Department of Mechanical and Aerospace Engineering', 'rizzoni.1@osu.edu', '930 Kinnear Road', '(614) 292-0734',
         'Electric vehicles, Energy management, Hybrid powertrains, Control systems',
         'Professor Rizzoni is a global authority on electrified transportation and energy management '
         'for hybrid and electric vehicles. He directs the Center for Automotive Research and has '
         'led numerous multi-million dollar collaborative projects with automotive partners.', False),
        ('Dr. Beth Plale', 'Professor and Executive Director', 'Department of Computer Science and Engineering', 'plale.1@osu.edu', '550 Dreese Lab', '(614) 292-1234',
         'Data science, Provenance, Research data management, Machine learning',
         'Professor Plale is Executive Director of the Translational Data Analytics Institute and '
         'leads research in data science, provenance, and research data management.', False),
        ('Dr. Linda Weavers', 'Professor and Chair', 'Department of Environmental Engineering', 'weavers.1@osu.edu', '470 Hitchcock Hall', '(614) 292-2006',
         'Water treatment, Sonochemistry, Environmental remediation, Emerging contaminants',
         'Professor Weavers is a leading expert in water treatment and sonochemical processes '
         'for environmental remediation. Her research addresses treatment of emerging contaminants '
         'including pharmaceuticals and PFAS.', False),
        ('Dr. Douglas Berman', 'Professor and Director', 'Department of Economics', 'berman.43@osu.edu', '55 W. 12th Avenue', '(614) 292-5925',
         'Criminal law, Sentencing, Drug policy, Prison policy',
         'Professor Berman is the nation\'s leading academic expert on federal sentencing law and '
         'drug policy reform. He founded and edits the widely read Sentencing Law and Policy blog '
         'and directs the Drug Enforcement and Policy Center.', False),
    ]

    for (name, title, dept_name, email, office, phone, interests, bio, emeritus) in faculty_data:
        dept_obj = departments.get(dept_name)
        m = Faculty(
            name=name,
            slug=slugify(name),
            title=title,
            department_id=dept_obj.id if dept_obj else None,
            email=email,
            office=office,
            phone=phone,
            research_interests=interests,
            bio=bio,
            is_emeritus=emeritus,
        )
        db.session.add(m)
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # ATHLETIC TEAMS
    # ─────────────────────────────────────────────────────────────────────────
    team_data = [
        ('Ohio State Buckeyes Football', 'Football', 'Men', 'Ryan Day', 'Ohio Stadium (Horseshoe)', 8, '11-2'),
        ('Ohio State Buckeyes Men\'s Basketball', 'Basketball', 'Men', 'Jake Diebler', 'Value City Arena', 0, '14-17'),
        ('Ohio State Buckeyes Women\'s Basketball', 'Basketball', 'Women', 'Kevin McGuff', 'Value City Arena', 0, '21-12'),
        ('Ohio State Buckeyes Baseball', 'Baseball', 'Men', 'Bill Mosiello', 'Bill Davis Stadium', 0, '35-22'),
        ('Ohio State Buckeyes Softball', 'Softball', 'Women', 'Kelly Kovach Schoenly', 'Buckeye Field', 0, '26-25'),
        ('Ohio State Buckeyes Men\'s Soccer', 'Soccer', 'Men', 'Brian Maisonneuve', 'Jesse Owens Memorial Stadium', 0, '7-10-3'),
        ('Ohio State Buckeyes Women\'s Soccer', 'Soccer', 'Women', 'Lori Walker', 'Jesse Owens Memorial Stadium', 0, '13-7-3'),
        ('Ohio State Buckeyes Men\'s Swimming & Diving', 'Swimming & Diving', 'Men', 'Bill Dorenkott', 'McCorkle Aquatic Pavilion', 12, '—'),
        ('Ohio State Buckeyes Women\'s Swimming & Diving', 'Swimming & Diving', 'Women', 'Bill Dorenkott', 'McCorkle Aquatic Pavilion', 11, '—'),
        ('Ohio State Buckeyes Men\'s Track & Field', 'Track & Field', 'Men', 'Ed Lomonaco', 'Jesse Owens Memorial Stadium', 0, '—'),
        ('Ohio State Buckeyes Women\'s Track & Field', 'Track & Field', 'Women', 'Ed Lomonaco', 'Jesse Owens Memorial Stadium', 0, '—'),
        ('Ohio State Buckeyes Volleyball', 'Volleyball', 'Women', 'Jen Flynn Oldenburg', 'Covelli Center', 0, '20-10'),
        ('Ohio State Buckeyes Wrestling', 'Wrestling', 'Men', 'Tom Ryan', 'Covelli Center', 8, '17-4'),
        ('Ohio State Buckeyes Men\'s Tennis', 'Tennis', 'Men', 'Ty Tucker', 'Ty Tucker Tennis Center', 0, '14-11'),
        ('Ohio State Buckeyes Women\'s Tennis', 'Tennis', 'Women', 'Melissa Schaub', 'Ty Tucker Tennis Center', 0, '16-9'),
        ('Ohio State Buckeyes Men\'s Golf', 'Golf', 'Men', 'Jay Moseley', 'OSU Golf Club', 0, '—'),
        ('Ohio State Buckeyes Women\'s Golf', 'Golf', 'Women', 'Therese Hession', 'OSU Golf Club', 0, '—'),
        ('Ohio State Buckeyes Men\'s Gymnastics', 'Gymnastics', 'Men', 'Miles Avery', 'Covelli Center', 0, '—'),
        ('Ohio State Buckeyes Women\'s Gymnastics', 'Gymnastics', 'Women', 'Bob Fetter', 'Covelli Center', 0, '—'),
        ('Ohio State Buckeyes Ice Hockey', 'Ice Hockey', 'Men', 'Steve Rohlik', 'Value City Arena', 0, '21-13-2'),
        ('Ohio State Buckeyes Men\'s Lacrosse', 'Lacrosse', 'Men', 'Nick Myers', 'Ohio Stadium (turf)', 0, '14-5'),
        ('Ohio State Buckeyes Women\'s Lacrosse', 'Lacrosse', 'Women', 'Nikki Hanigan', 'Buckeye Field (lacrosse)', 0, '8-10'),
        ('Ohio State Buckeyes Field Hockey', 'Field Hockey', 'Women', 'Jarred Martin', 'Buckeye Field', 0, '12-8'),
        ('Ohio State Buckeyes Rowing', 'Rowing', 'Women', 'Emanuele Catasta', 'Griggs Reservoir', 0, '—'),
        ('Ohio State Buckeyes Fencing', 'Fencing', 'Men', 'George Shutt', 'RPAC', 2, '—'),
        ('Ohio State Buckeyes Women\'s Fencing', 'Fencing', 'Women', 'George Shutt', 'RPAC', 0, '—'),
    ]

    for (name, sport, gender, coach, venue, titles, record) in team_data:
        t = AthleticTeam(
            name=name,
            slug=slugify(name),
            sport=sport,
            gender=gender,
            conference='Big Ten',
            coach=coach,
            home_venue=venue,
            national_titles=titles,
            recent_record=record,
        )
        db.session.add(t)
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # NEWS ARTICLES
    # ─────────────────────────────────────────────────────────────────────────
    now = datetime(2024, 10, 15)
    articles = [
        ('Ohio State Researchers Develop Breakthrough Cancer Immunotherapy', 'Research',
         'Jody Sheridan', now - timedelta(days=2), True,
         'Ohio State, immunotherapy, cancer, James Cancer Hospital, research',
         'A team of Ohio State researchers has achieved a major breakthrough in cancer immunotherapy, '
         'developing a novel approach that could improve outcomes for patients with hard-to-treat solid tumors.',
         'Ohio State researchers led by Dr. William Farrar at the James Cancer Hospital and Solove Research Institute '
         'have developed a new CAR-T cell therapy that targets multiple tumor antigens simultaneously, '
         'addressing one of the key limitations of current immunotherapy approaches.\n\n'
         'In preclinical studies, the multi-antigen approach demonstrated a 73 percent reduction in tumor burden '
         'compared to conventional single-antigen CAR-T therapy. Researchers are now planning a Phase I clinical '
         'trial expected to begin enrollment in early 2025.\n\n'
         '"This represents a fundamental advance in how we design cellular therapies for solid tumors," '
         'said Dr. Farrar. "By targeting multiple antigens, we make it much harder for cancer cells to '
         'develop resistance through antigen escape."\n\n'
         'The research was published in Nature Medicine and was supported by grants from the National Cancer '
         'Institute and the Ohio State University Comprehensive Cancer Center.'),
        ('Ohio State Football Ranked in Top 5 Heading into Conference Play', 'Athletics',
         'Mike Cardamone', now - timedelta(days=3), True,
         'football, Buckeyes, Big Ten, ranking, Ryan Day',
         'The Ohio State Buckeyes football team has climbed into the top five of both major polls '
         'as they enter the heart of Big Ten Conference play.',
         'The Ohio State Buckeyes have moved into the top five of the AP Poll and the Coaches Poll '
         'after a dominant performance in their non-conference schedule. Coach Ryan Day\'s squad '
         'has outscored opponents by an average of 34 points per game.\n\n'
         '"We\'re playing complementary football right now," Day said at his Monday press conference. '
         '"The offense is efficient, the defense is flying around, and the special teams have been outstanding."\n\n'
         'Quarterback Will Howard has emerged as a Heisman Trophy candidate, completing 72 percent of '
         'his passes for 1,847 yards and 18 touchdowns against just two interceptions.\n\n'
         'The Buckeyes host Michigan State this Saturday at Ohio Stadium, with kickoff set for noon '
         'on Fox. The game is a sold-out affair, with over 105,000 fans expected to fill the Horseshoe.'),
        ('Fisher College of Business Launches New Sustainability MBA Track', 'Campus Life',
         'OSU News Staff', now - timedelta(days=5), False,
         'Fisher, MBA, sustainability, business, environment',
         'Fisher College of Business has unveiled a new MBA specialization in Sustainable Business, '
         'responding to growing demand from employers for business leaders with expertise in ESG.',
         'Fisher College of Business has announced the launch of a new Sustainable Business specialization '
         'within its full-time MBA program, beginning in the 2025-2026 academic year.\n\n'
         'The specialization will allow MBA students to develop expertise in environmental, social, and '
         'governance (ESG) strategy, sustainable supply chains, green finance, and corporate sustainability reporting.\n\n'
         '"Employers are increasingly looking for business leaders who understand how sustainability creates '
         'long-term value," said Dean Anil Makhija. "This specialization gives our students a competitive '
         'advantage in a rapidly evolving landscape."\n\n'
         'The program includes case studies from Fortune 500 companies, a sustainability consulting practicum '
         'with Ohio-based organizations, and access to Fisher\'s extensive alumni network in sustainable business.'),
        ('Ohio Supercomputer Center Upgrades to Exascale-Class Computing', 'Research',
         'OSU News Staff', now - timedelta(days=7), False,
         'Ohio Supercomputer Center, HPC, computing, research infrastructure',
         'The Ohio Supercomputer Center has completed a major infrastructure upgrade, bringing '
         'near-exascale computing capabilities to Ohio researchers.',
         'The Ohio Supercomputer Center has announced the successful deployment of Ascend, a new '
         'high-performance computing cluster that dramatically expands computational capacity for '
         'Ohio researchers.\n\n'
         'Ascend features 680 compute nodes with NVIDIA H100 GPUs, delivering over 50 petaflops of '
         'AI-optimized computing power — a tenfold increase over the previous system. The system also '
         'includes 10 petabytes of high-speed parallel storage.\n\n'
         '"Ascend positions Ohio at the forefront of academic computing," said Director David Bickel. '
         '"Researchers can now tackle AI, climate modeling, drug discovery, and genomics problems '
         'that were previously out of reach."'),
        ('Ohio State Alumnus Appointed to NASA Administrator Role', 'Faculty',
         'OSU News Staff', now - timedelta(days=9), False,
         'alumni, NASA, space, science, engineering',
         'An Ohio State University alumnus with degrees in aerospace engineering and public policy '
         'has been appointed to a senior leadership role at the National Aeronautics and Space Administration.',
         'Dr. James Crawford, who earned his BS in Aerospace Engineering from Ohio State in 1994 and his '
         'MPH from the John Glenn College of Public Affairs in 2002, has been appointed as Deputy Associate '
         'Administrator for Research at NASA.\n\n'
         '"Ohio State gave me the foundation to dream big and the tools to make those dreams real," '
         'Crawford said upon his appointment. "I carry the Buckeye spirit into everything I do."'),
        ('College of Engineering Receives $50M Federal Grant for Hydrogen Research', 'Research',
         'College of Engineering Communications', now - timedelta(days=11), True,
         'engineering, hydrogen, energy, federal grant, NSF, research',
         'The Ohio State College of Engineering has been awarded a $50 million Department of Energy '
         'grant to establish a national center for clean hydrogen research.',
         'The Ohio State College of Engineering has secured a $50 million grant from the Department of '
         'Energy to establish the National Center for Clean Hydrogen Technologies, led by Professor '
         'Yann Guezennec of the Center for Clean Hydrogen.\n\n'
         'The center will bring together researchers from engineering, chemistry, environmental engineering, '
         'and public policy to accelerate the transition to a hydrogen economy.\n\n'
         '"Hydrogen is one of the most promising pathways to deep decarbonization," said Dean Ayanna Howard. '
         '"This investment reflects Ohio State\'s leadership in clean energy research and positions us to '
         'deliver real-world impact at scale."'),
        ('Moritz College of Law Hosts National Symposium on Artificial Intelligence and Law', 'Campus Life',
         'Moritz Communications', now - timedelta(days=14), False,
         'law, AI, artificial intelligence, symposium, Moritz',
         'Moritz College of Law welcomed leading legal scholars, judges, and technologists for a '
         'two-day national symposium on the intersection of artificial intelligence and legal practice.',
         'Moritz College of Law hosted more than 200 legal scholars, practicing attorneys, federal judges, '
         'and technology experts at its inaugural AI and Law Symposium, exploring how machine learning '
         'is transforming legal research, evidence, and decision-making.\n\n'
         'Keynote speakers included a federal circuit court judge who spoke about AI-assisted legal research, '
         'and a leading AI ethicist who addressed bias and fairness in algorithmic decision systems.\n\n'
         'Symposium papers will be published in a special issue of the Ohio State Law Journal in spring 2025.'),
        ('Ohio State Named Among Top 20 Public Universities by U.S. News', 'Campus Life',
         'OSU News Staff', now - timedelta(days=16), True,
         'ranking, U.S. News, public university, research',
         'The Ohio State University has been ranked among the top 20 public universities in the '
         'United States in the latest U.S. News & World Report Best Colleges rankings.',
         'Ohio State maintained its position among the top 20 public universities in the country according '
         'to the 2025 U.S. News & World Report Best Colleges rankings, continuing its streak of '
         'consistent improvement over the past decade.\n\n'
         'Several individual programs also saw strong rankings: Computer Science moved into the top 15 '
         'nationally; the Moritz College of Law climbed to #26; and the Fisher College of Business MBA '
         'program is now ranked #28 in the nation.\n\n'
         '"These rankings reflect the hard work of our faculty, staff, and students," said Provost Melissa Gilliam. '
         '"But more importantly, they reflect our commitment to providing a world-class education and '
         'conducting research that matters."'),
        ('TDAI Launches Interdisciplinary Health Data Science Training Program', 'Research',
         'TDAI Communications', now - timedelta(days=18), False,
         'TDAI, data science, health, training, interdisciplinary',
         'The Translational Data Analytics Institute has launched a new graduate training program '
         'that brings together doctoral students from medicine, public health, statistics, and computer science.',
         'The Translational Data Analytics Institute has launched the Health Data Science Training Program, '
         'a multi-year initiative funded by the National Institutes of Health to train the next generation '
         'of health data scientists.\n\n'
         'The program provides 15 doctoral fellows per cohort with interdisciplinary coursework, mentored '
         'research experiences, and professional development in communication, ethics, and entrepreneurship.\n\n'
         '"Health data science requires expertise that no single discipline can provide," said Director Beth Plale. '
         '"This program creates researchers who can bridge clinical medicine, public health, and advanced computing."'),
        ('Buckeyes Wrestling Team Ranked No. 1 in the Nation', 'Athletics',
         'OSU Athletics Communications', now - timedelta(days=20), False,
         'wrestling, ranking, national, Buckeyes, Tom Ryan',
         'The Ohio State wrestling team has opened the season as the No. 1 ranked team in the '
         'nation, setting sights on a record-breaking national championship run.',
         'Ohio State wrestling began the 2024-25 season ranked No. 1 in the country by InterMat '
         'and FloWrestling, led by a roster of 11 nationally ranked wrestlers including three '
         'returning All-Americans.\n\n'
         '"This team has the talent and the hunger to be special," said head coach Tom Ryan, who '
         'has led the Buckeyes to 8 national championships. "But rankings don\'t win titles — '
         'hard work and execution do."'),
        ('Ohio State Sets Record for Research Expenditures at $1.3 Billion', 'Research',
         'Office of Research Communications', now - timedelta(days=22), True,
         'research, expenditure, record, funding, grants',
         'Ohio State has reached a historic milestone, surpassing $1.3 billion in annual research '
         'expenditures for the first time in the university\'s 154-year history.',
         'The Ohio State University has reported a record $1.3 billion in research expenditures for '
         'fiscal year 2024, according to data compiled by the Office of Research. This represents a '
         'seven percent increase over the previous year and marks the university\'s highest-ever '
         'research investment.\n\n'
         'Funding came from federal agencies including NIH, NSF, DOE, and DOD; state of Ohio; '
         'industry partners; and private foundations.\n\n'
         '"This milestone demonstrates the remarkable breadth and quality of research happening at '
         'Ohio State," said President Ted Carter. "Our faculty are tackling the challenges that '
         'matter most — cancer, climate, artificial intelligence, and so much more."'),
        ('College of Nursing Launches Mental Health Initiative for Students', 'Health',
         'College of Nursing Communications', now - timedelta(days=25), False,
         'nursing, mental health, students, wellness, Bernadette Melnyk',
         'The College of Nursing, led by Dean Bernadette Melnyk, has launched a comprehensive '
         'mental health and wellness initiative targeting Ohio State\'s student population.',
         'The Ohio State College of Nursing has launched "Buckeye Wellness," a university-wide '
         'evidence-based program designed to improve mental health, well-being, and academic '
         'outcomes for students.\n\n'
         'The program, developed by Dean Bernadette Melnyk and her team, provides students with '
         'a seven-week cognitive behavioral skills-building intervention via a mobile application, '
         'peer support groups, and faculty wellness champions.\n\n'
         'Early pilot data showed a 22 percent reduction in depression and anxiety symptoms among '
         'participating students and a significant improvement in GPAs compared to a control group.'),
        ('Ohio State Hosts International Climate Summit Ahead of COP30', 'Research',
         'Sustainability Institute', now - timedelta(days=28), False,
         'climate, sustainability, international, COP, environment',
         'The Ohio State Sustainability Institute welcomed climate researchers and policymakers '
         'from 40 countries for a pre-COP30 research summit at the Columbus campus.',
         'Ohio State\'s Sustainability Institute hosted the Global Universities Climate Summit, '
         'bringing together 300 climate scientists, economists, engineers, and policymakers from '
         '40 nations to share research and develop recommendations ahead of the UN Climate '
         'Conference (COP30).\n\n'
         '"Universities play a unique role in the climate challenge — we produce the knowledge '
         'and the people who will deliver solutions," said Institute Director Dr. Julie Newman. '
         '"This summit strengthens the global network of researchers committed to a just and '
         'sustainable future."\n\n'
         'Summit participants issued a joint statement calling for accelerated decarbonization '
         'of electricity systems, food security investments, and equitable climate finance.'),
        ('Department of Computer Science Launches AI Ethics Certificate', 'Student',
         'CSE Department Communications', now - timedelta(days=31), False,
         'CSE, AI, ethics, certificate, students',
         'The Department of Computer Science and Engineering has introduced a new undergraduate '
         'certificate in Artificial Intelligence Ethics, open to students across all colleges.',
         'Ohio State\'s Department of Computer Science and Engineering has launched an undergraduate '
         'Certificate in AI Ethics, a 15-credit interdisciplinary program available to students in '
         'any major.\n\n'
         'The certificate curriculum draws on coursework from computer science, philosophy, law, '
         'sociology, and public policy, preparing students to develop and deploy AI systems '
         'responsibly.\n\n'
         '"AI is being embedded into every sector of society, and we need graduates who understand '
         'both the technical and ethical dimensions," said Department Chair Dr. Srinivasan Parthasarathy.'),
        ('Ohio State Veterinary Medical Center Treats Record Number of Patients', 'Health',
         'College of Veterinary Medicine', now - timedelta(days=35), False,
         'veterinary, Vet Medical Center, patients, animals, care',
         'The Ohio State Veterinary Medical Center has seen a record 86,000 patient visits in '
         'the past year, reinforcing its reputation as one of the nation\'s premier veterinary '
         'teaching hospitals.',
         'The Ohio State University Veterinary Medical Center reported 86,231 patient visits '
         'in fiscal year 2024, a 12 percent increase over the previous year and a new all-time record.\n\n'
         'The VMC offers specialty services across cardiology, dermatology, emergency medicine, '
         'neurology, oncology, surgery, and more than 25 other disciplines for companion animals, '
         'horses, and farm animals.\n\n'
         '"Our growth reflects both the exceptional quality of our clinical teams and the trust '
         'that pet owners across the region place in Ohio State," said Dean Rustin Moore.'),
        ('Ohio State Announces New Partnership with Nationwide Children\'s Hospital', 'Health',
         'OSU Medical Center Communications', now - timedelta(days=40), False,
         'Nationwide Children\'s, partnership, pediatrics, medical center, research',
         'Ohio State and Nationwide Children\'s Hospital have formalized a landmark partnership '
         'to advance pediatric research, education, and clinical care.',
         'The Ohio State University and Nationwide Children\'s Hospital have signed a comprehensive '
         'partnership agreement that strengthens research, training, and patient care collaborations '
         'between the two institutions.\n\n'
         'Under the agreement, Ohio State medical faculty will hold joint appointments at Nationwide '
         'Children\'s, and residents in pediatrics will have expanded training opportunities at both '
         'institutions.\n\n'
         '"Together, Ohio State and Nationwide Children\'s are a powerhouse for children\'s health '
         'in this region and nationally," said OSU President Ted Carter.'),
        ('Buckeyes Swimming and Diving Teams Win Big Ten Championships', 'Athletics',
         'OSU Athletics Communications', now - timedelta(days=45), True,
         'swimming, diving, Big Ten, championship, Buckeyes',
         'Ohio State\'s men\'s and women\'s swimming and diving teams both captured Big Ten '
         'Conference championships in dramatic fashion at the annual championships meet.',
         'Ohio State\'s swimming and diving programs claimed a sweep of the Big Ten championships, '
         'with both the men\'s and women\'s teams winning conference titles for the second consecutive year.\n\n'
         'The men\'s team finished with 1,342.5 points, edging Michigan by 43 points, '
         'while the women\'s team dominated with a 260-point margin of victory.\n\n'
         'Coach Bill Dorenkott\'s program has now won a combined 23 Big Ten championships.'),
        ('Graduate School Expands Fellowship Opportunities for Doctoral Students', 'Student',
         'Graduate School Communications', now - timedelta(days=50), False,
         'graduate school, fellowship, doctoral, funding, PhD',
         'Ohio State\'s Graduate School has announced a $25 million expansion of fellowship '
         'funding for doctoral students, aiming to increase diversity and reduce time to degree.',
         'Ohio State\'s Graduate School has announced the Buckeye Graduate Excellence Initiative, '
         'a $25 million commitment over five years to expand fellowship support for doctoral students.\n\n'
         'The initiative will fund 150 additional university fellowships annually, with a particular '
         'emphasis on recruiting students from underrepresented backgrounds and high-priority '
         'research areas including AI, climate science, and biomedical engineering.\n\n'
         '"Graduate students are the engine of our research enterprise," said Dean Sean Carson. '
         '"This investment ensures Ohio State can recruit and support the best and brightest from '
         'across the country and the world."'),
        ('Ohio State Extension Celebrates 100 Years of Service to Ohio Communities', 'Campus Life',
         'OSU Extension Communications', now - timedelta(days=55), False,
         'extension, Ohio, community, centennial, agriculture',
         'Ohio State University Extension is marking its centennial year with events across '
         'all 88 Ohio counties, celebrating a century of research-based service to Ohioans.',
         'Ohio State University Extension is celebrating its 100th anniversary as an official '
         'federal-state-local partnership, with events and programs planned across all 88 '
         'Ohio counties throughout the academic year.\n\n'
         'Extension educators serve nearly every Ohio family through programs in agriculture, '
         'family and consumer sciences, 4-H youth development, and community development.\n\n'
         '"Extension connects the resources of Ohio State University directly to Ohioans wherever '
         'they live," said College Dean Cathann Kress. "For 100 years, we have been a trusted '
         'partner in making Ohio stronger."'),
        ('Ohio State Partners with Intel on $200M Semiconductor Research Initiative', 'Research',
         'College of Engineering Communications', now - timedelta(days=60), True,
         'Intel, semiconductor, engineering, partnership, industry',
         'Ohio State University and Intel Corporation have announced a landmark $200 million '
         'research partnership focused on next-generation semiconductor technology.',
         'Ohio State and Intel Corporation have announced a $200 million, 10-year research '
         'partnership to advance semiconductor science and engineering.\n\n'
         'The collaboration will support research in chip design, manufacturing, materials science, '
         'and workforce development, leveraging Intel\'s planned Ohio semiconductor fabrication '
         'facilities in Licking County.\n\n'
         '"This partnership is transformative for Ohio State and for the state of Ohio," said '
         'Dean Ayanna Howard. "It connects world-class academic research directly to the largest '
         'semiconductor investment in American history."\n\n'
         'The agreement includes joint faculty appointments, student internship pipelines, shared '
         'laboratory facilities, and collaborative research grants.'),
    ]

    for (title, cat, author, pub_date, featured, tags, summary, content) in articles:
        a = NewsArticle(
            title=title,
            slug=slugify(title),
            category=cat,
            author=author,
            published_date=pub_date,
            featured=featured,
            tags=tags,
            summary=summary,
            content=content,
            view_count=0,
        )
        db.session.add(a)
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # EVENTS
    # ─────────────────────────────────────────────────────────────────────────
    future = datetime(2024, 11, 1)
    events = [
        ('Buckeyes vs. Michigan State Football', 'Sports',
         future + timedelta(days=2), future + timedelta(days=2, hours=3, minutes=30),
         'Ohio Stadium', 'Ohio Stadium (The Horseshoe)', 'Columbus', 'OSU Athletics', False, 'Varies',
         'Come out to the Horseshoe as the Buckeyes take on the Michigan State Spartans in a key Big Ten '
         'matchup. Enjoy pre-game festivities starting two hours before kickoff, including live music and '
         'alumni tailgating. This is a sold-out game — tickets required.'),
        ('Ohio State Research Forum: AI in Health Care', 'Lecture',
         future + timedelta(days=5), future + timedelta(days=5, hours=2),
         'Biomedical Research Tower, Room 105', 'Biomedical Research Tower', 'Columbus', 'TDAI', True, 'Free',
         'Leading researchers from medicine, nursing, and computer science will present their work on '
         'applying artificial intelligence to clinical decision support, medical imaging analysis, '
         'and population health management. Lunch will be provided for registered attendees.'),
        ('Annual Buckeye Career Fair — Engineering and Technology', 'Career',
         future + timedelta(days=8), future + timedelta(days=8, hours=5),
         'Ohio Union', 'Ohio Union', 'Columbus', 'Engineering Career Services', True, 'Free',
         'Over 200 companies recruiting Ohio State students for internships, co-ops, and full-time '
         'positions in engineering, technology, and related fields. Dress professionally and bring '
         'multiple copies of your resume. Business casual or professional attire required.'),
        ('Wexner Arts Center Performance: International Dance Festival', 'Arts',
         future + timedelta(days=10), future + timedelta(days=10, hours=2),
         'Wexner Center for the Arts', 'Mershon Auditorium', 'Columbus', 'Wexner Center', False, '$15-35',
         'The Wexner Center\'s International Dance Festival presents world-renowned dance companies '
         'in an evening of contemporary and classical works. This year features companies from '
         'Brazil, South Korea, and France. Tickets available at the Wexner Center box office.'),
        ('Ohio State Farmers Market', 'Social',
         future + timedelta(days=12), future + timedelta(days=12, hours=3),
         'Tuttle Park Place', 'Tuttle Park', 'Columbus', 'OSU Sustainability Institute', False, 'Free',
         'The weekly Ohio State Farmers Market features fresh produce, artisan foods, and '
         'handcrafted goods from local farmers and makers. Free to attend, cash and card accepted '
         'at most vendors. Open to the campus community and Columbus neighbors.'),
        ('Graduate Admissions Open House — College of Engineering', 'Lecture',
         future + timedelta(days=15), future + timedelta(days=15, hours=3),
         'Dreese Laboratory Atrium', 'Dreese Lab', 'Columbus', 'Graduate School', True, 'Free',
         'Prospective graduate students in engineering are invited to learn about MS and PhD programs, '
         'research opportunities, fellowship funding, and campus life at Ohio State. Department faculty '
         'and current graduate students will be available for Q&A.'),
        ('Infectious Disease Grand Rounds: Lessons from COVID-19', 'Lecture',
         future + timedelta(days=18), future + timedelta(days=18, hours=1, minutes=30),
         'Meiling Hall Auditorium', 'Meiling Hall', 'Columbus', 'Infectious Disease Institute', False, 'Free',
         'Dr. Michael Oglesbee of the Infectious Disease Institute will lead a discussion on '
         'surveillance, vaccine distribution, and pandemic preparedness lessons drawn from the '
         'COVID-19 pandemic response. CME credit available for health care professionals.'),
        ('Ohio State Women\'s Basketball Home Opener', 'Sports',
         future + timedelta(days=20), future + timedelta(days=20, hours=2),
         'Value City Arena', 'Value City Arena', 'Columbus', 'OSU Athletics', False, 'Varies',
         'Cheer on the Buckeyes as the women\'s basketball team opens their home schedule at '
         'Value City Arena. The team is led by experienced coach Kevin McGuff and returns several '
         'key contributors from last year\'s NCAA Tournament team. Student tickets available.'),
        ('Presidential Lecture Series: Dr. Ayanna Howard on Ethical AI', 'Lecture',
         future + timedelta(days=23), future + timedelta(days=23, hours=1, minutes=30),
         'Research Commons, 18th Avenue Library', 'Libraries', 'Columbus', 'Office of Academic Affairs', False, 'Free',
         'Dean of Engineering Ayanna Howard presents a public lecture on the ethical dimensions '
         'of artificial intelligence, drawing on her research in human-machine interaction and '
         'algorithmic bias. This event is free and open to the campus community and the public.'),
        ('Fisher College of Business Startup Competition Finals', 'Career',
         future + timedelta(days=26), future + timedelta(days=26, hours=4),
         'Pfahl Hall Auditorium', 'Fisher Hall', 'Columbus', 'Fisher Entrepreneurship', True, 'Free',
         'Watch as student entrepreneurs pitch their companies to a panel of investors and business '
         'leaders in the annual Fisher Startup Competition finals. Over $50,000 in prize money '
         'and investment opportunities at stake. Open to the public — seats are limited.'),
        ('Autumn Hike at Chadwick Arboretum', 'Social',
         future + timedelta(days=29), future + timedelta(days=29, hours=2),
         'Chadwick Arboretum, 2001 Fyffe Court', 'Chadwick Arboretum', 'Columbus', 'Chadwick Arboretum', False, 'Free',
         'Enjoy a guided autumn hike through the Chadwick Arboretum with naturalist educators '
         'highlighting seasonal plant changes, migratory birds, and sustainable landscaping practices. '
         'Free and open to all — no registration required. Dogs welcome on leash.'),
        ('Ohio Supercomputer Center Research Computing Workshop', 'Lecture',
         future + timedelta(days=32), future + timedelta(days=32, hours=6),
         'Baker Systems Engineering Building', 'Baker Systems', 'Columbus', 'Ohio Supercomputer Center', True, 'Free',
         'Full-day workshop covering Ohio Supercomputer Center resources, job submission, '
         'parallel programming, and GPU computing for research. Ideal for graduate students '
         'and postdocs new to high-performance computing. Lunch provided for registered attendees.'),
        ('CFAES Annual Farm Science Review', 'Social',
         future + timedelta(days=40), future + timedelta(days=40, hours=8),
         'Molly Caren Agricultural Center', 'Molly Caren Agricultural Center', 'London',
         'CFAES Extension', False, '$15',
         'The Farm Science Review is one of the nation\'s largest agricultural shows, featuring '
         'field demonstrations of the latest farm equipment, crop technologies, and agronomy '
         'research. Held at the 1,000-acre Molly Caren Agricultural Center near London, Ohio.'),
        ('Mental Health Awareness Week: Buckeye Wellness Fair', 'Health',
         future + timedelta(days=7), future + timedelta(days=7, hours=4),
         'Ohio Union Great Hall', 'Ohio Union', 'Columbus', 'Student Life Counseling and Consultation Service', False, 'Free',
         'Ohio State\'s annual Mental Health Awareness Week features a wellness fair with '
         'information about campus counseling resources, peer support programs, mindfulness '
         'workshops, and interactive activities promoting mental well-being. All students welcome.'),
        ('Law Review Symposium: Technology, Privacy, and the Law', 'Lecture',
         future + timedelta(days=35), future + timedelta(days=35, hours=8),
         'Drinko Hall Auditorium', 'Moritz College of Law', 'Columbus', 'Ohio State Law Journal', True, 'Free',
         'The Ohio State Law Journal\'s annual symposium brings together leading scholars and '
         'practitioners to examine legal frameworks around data privacy, surveillance, '
         'algorithmic decision-making, and digital rights. CLE credit available.'),
        ('Virtual Info Session: Online MPH Program', 'Virtual',
         future + timedelta(days=14), future + timedelta(days=14, hours=1),
         'Zoom (link provided upon registration)', 'Online', 'Columbus',
         'College of Public Health', True, 'Free',
         'Learn about Ohio State\'s online Master of Public Health program, including curriculum, '
         'admissions requirements, financial aid, and student experience. Faculty and current '
         'students will be available to answer questions. Registration required to receive Zoom link.'),
    ]

    for (title, cat, start, end, location, building, campus, organizer, reg_req, cost, desc) in events:
        e = Event(
            title=title,
            description=desc,
            start_datetime=start,
            end_datetime=end,
            location=location,
            building=building,
            campus=campus,
            category=cat,
            organizer=organizer,
            registration_required=reg_req,
            cost=cost,
        )
        db.session.add(e)
    db.session.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # BENCHMARK USERS
    # ─────────────────────────────────────────────────────────────────────────
    if not User.query.filter_by(email='alice@osu.edu').first():
        for username, name, email, role in [
            ('alice', 'Alice Anderson', 'alice@osu.edu', 'student'),
            ('bob', 'Bob Baker', 'bob@osu.edu', 'student'),
            ('carol', 'Carol Chen', 'carol@osu.edu', 'faculty'),
            ('dave', 'Dave Davis', 'dave@osu.edu', 'staff'),
        ]:
            u = User(username=username, email=email, full_name=name, role=role)
            u.set_password('test1234')
            db.session.add(u)
        db.session.flush()

    db.session.commit()
