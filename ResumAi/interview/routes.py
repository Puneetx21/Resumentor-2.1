from flask import Blueprint, render_template, session, request, jsonify, url_for, redirect, flash, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename
import time
import json
import os
import random
import pdfplumber
from datetime import datetime
from statistics import mean

from ResumAi.models import Resume, InterviewSession, InterviewQuestion, InterviewResponse
from ResumAi.extensions import db
from ResumAi.keywords import TECH_ROLE_KEYWORDS
from ResumAi.resume.reporting import generate_interview_report_pdf
from ResumAi.interview.questions_extended import EXTENDED_ROLE_QUESTIONS
from ResumAi.interview.resume_questions import parse_resume_for_interview

interview_bp = Blueprint('interview', __name__)


ROUND_LABELS = {
    'intro': 'Introduction Round',
    'technical': 'Technical Round',
    'pressure': 'Pressure Handling Round',
}


INTRO_QUESTIONS = [
    'Introduce yourself in 60-90 seconds and highlight your strongest professional achievements.',
    'Walk me through your most relevant project and your exact ownership in it.',
    'Why are you targeting this role now, and what value will you bring in the first 90 days?',
    'How do your strengths and areas for improvement shape your day-to-day work?',
    'How do teammates usually describe your collaboration and communication style?',
]


PRESSURE_QUESTIONS = [
    'A production issue happens five minutes before a release. How do you handle it?',
    'Two critical tasks have the same deadline and limited resources. How do you prioritize?',
    'Your manager disagrees with your technical approach in a high-pressure meeting. How do you respond?',
]


TECHNICAL_PROMPTS = [
    'Explain how you have used {keyword} in a real project, including one tradeoff you handled.',
    'If you had to design a production-ready component around {keyword}, what architecture would you choose and why?',
    'What are common mistakes teams make with {keyword}, and how do you avoid them?',
    'How do you test and debug systems that rely on {keyword}?',
    'Describe one performance optimization you implemented involving {keyword}.',
    'What security or reliability considerations matter most when using {keyword}?',
    'How do you decide when to use {keyword} versus an alternative?',
    'Give a practical example where {keyword} improved user or business outcomes.',
    'How would you mentor a junior engineer to become effective with {keyword}?',
    'What metrics would you track to evaluate success when using {keyword}?',
    'Describe a difficult bug related to {keyword} and how you resolved it.',
    'What scaling challenges can appear with {keyword}, and how would you mitigate them?',
]


ROLE_QUESTIONS = {
    'frontend-developer': [
        'How do you decide between React, Vue, and Angular for a new project? Walk me through your decision framework.',
        'Explain how the virtual DOM works and why it matters for performance in modern frontend frameworks.',
        'Describe your approach to making a complex web application fully responsive and accessible (WCAG compliant).',
        'How do you handle state management in a large single-page application? Compare at least two approaches you have used.',
        'Walk me through how you would optimize a page that scores below 50 on Lighthouse performance.',
        'Explain the CSS box model, specificity rules, and how you avoid styling conflicts in a large codebase.',
        'How do you implement lazy loading, code splitting, and tree shaking in a production frontend build?',
        'Describe how you handle cross-browser compatibility issues and what tools you use for testing.',
        'How do you structure component hierarchies and prop flows to keep a frontend project maintainable over time?',
        'Explain how you handle authentication flows (login, token refresh, protected routes) on the frontend.',
        'What is your strategy for writing and organizing unit tests and integration tests for UI components?',
        'How do you handle API error states, loading indicators, and optimistic UI updates in a frontend app?',
    ],
    'backend-developer': [
        'Design a RESTful API for a multi-tenant SaaS application. How do you handle tenant isolation and authentication?',
        'Explain the differences between SQL and NoSQL databases. When would you choose one over the other?',
        'How do you design and implement database migrations in a production system with zero downtime?',
        'Describe your approach to implementing rate limiting and API throttling to prevent abuse.',
        'How do you handle background job processing and task queues in a backend system?',
        'Walk me through how you would debug a memory leak in a production backend service.',
        'Explain how you implement caching strategies (Redis, Memcached) and handle cache invalidation.',
        'How do you design an authentication and authorization system with role-based access control (RBAC)?',
        'Describe your approach to logging, monitoring, and alerting in a distributed backend architecture.',
        'How would you design a file upload service that handles large files reliably and securely?',
        'Explain how you handle database connection pooling and optimize query performance under high load.',
        'How do you implement API versioning and maintain backward compatibility for existing clients?',
    ],
    'fullstack-developer': [
        'How do you decide which logic belongs on the frontend versus the backend in a full-stack application?',
        'Design the architecture for a real-time collaborative document editing application. Cover both frontend and backend.',
        'How do you handle authentication across a React frontend and Node.js backend using JWTs?',
        'Explain your approach to deploying a full-stack application with Docker and CI/CD pipelines.',
        'How do you manage shared data models and validation rules between the frontend and backend?',
        'Describe how you would implement server-side rendering (SSR) and explain when it is appropriate.',
        'How do you handle file uploads from a frontend form through to backend storage and retrieval?',
        'Walk me through how you would set up a monorepo or multi-repo structure for a full-stack project.',
        'How do you implement real-time features (WebSockets, SSE) across the full stack?',
        'Describe your approach to error handling that covers frontend display, API responses, and server logs.',
        'How do you optimize the performance of a full-stack app that has slow page loads and API latencies?',
        'Explain how you handle database schema changes when the frontend depends on specific API response shapes.',
    ],
    'web-developer': [
        'Explain the critical rendering path in a browser and how you optimize it for faster page loads.',
        'How do you implement SEO best practices in a modern web application?',
        'Describe the difference between server-side rendering, client-side rendering, and static site generation.',
        'How do you handle form validation on both the client and server side? Why is server-side validation mandatory?',
        'Walk me through how HTTP/2 and HTTP/3 improve web performance compared to HTTP/1.1.',
        'How do you implement a Progressive Web App (PWA) with offline support and push notifications?',
        'Explain how you handle CORS issues and configure secure cross-origin requests.',
        'How do you structure HTML semantically and why does it matter for accessibility and SEO?',
        'Describe your workflow for debugging layout issues across different browsers and devices.',
        'How do you implement web security measures like CSP, HTTPS enforcement, and XSS prevention?',
        'Explain how you use service workers and what caching strategies they support.',
        'How would you migrate a legacy jQuery application to a modern framework incrementally?',
    ],
    'python-developer': [
        'Explain Python\'s GIL (Global Interpreter Lock) and how it affects multi-threaded applications.',
        'How do you structure a large Python project with proper packaging, imports, and dependency management?',
        'Describe the differences between Django, Flask, and FastAPI. When would you choose each?',
        'How do you write effective unit tests in Python using pytest, including fixtures and parametrize?',
        'Explain Python decorators with a real-world example of how you used one in production.',
        'How do you handle async programming in Python using asyncio? Give a practical use case.',
        'Describe your approach to profiling and optimizing slow Python code.',
        'How do you manage virtual environments and dependencies in a team setting?',
        'Explain how Python\'s memory management and garbage collection work.',
        'How do you implement type hints effectively and integrate mypy into your workflow?',
        'Describe a data processing pipeline you built using pandas or similar libraries.',
        'How do you handle database interactions in Python using ORMs like SQLAlchemy versus raw SQL?',
    ],
    'java-developer': [
        'Explain the differences between Spring Boot and traditional Spring Framework. Why has Spring Boot become standard?',
        'How do you design and implement microservices architecture using Spring Cloud components?',
        'Describe Java\'s memory model, garbage collection strategies, and how you tune JVM performance.',
        'How do you implement dependency injection in Spring and why is it important for testability?',
        'Walk me through how you handle exception handling patterns in a Java REST API.',
        'Explain the Java Collections framework and when you would choose different data structures.',
        'How do you implement database access with Hibernate/JPA, including lazy loading and N+1 problem solutions?',
        'Describe your approach to writing unit and integration tests with JUnit 5 and Mockito.',
        'How do you implement concurrent programming in Java using threads, executors, and CompletableFuture?',
        'Explain how you handle configuration management and profiles in a Spring Boot application.',
        'How do you secure a Java application using Spring Security with OAuth2 and JWT?',
        'Describe your experience with build tools (Maven/Gradle) and how you manage multi-module projects.',
    ],
    'cpp-developer': [
        'Explain RAII (Resource Acquisition Is Initialization) and how it prevents resource leaks in C++.',
        'How do smart pointers (unique_ptr, shared_ptr, weak_ptr) work and when do you use each?',
        'Describe the differences between stack and heap memory allocation and their performance implications.',
        'How do you design and implement multithreaded applications in C++ using std::thread and synchronization primitives?',
        'Explain move semantics and perfect forwarding in C++11 and beyond.',
        'How do you use the STL effectively, including iterators, algorithms, and custom comparators?',
        'Describe your approach to debugging memory corruption, segfaults, and undefined behavior.',
        'How do you write exception-safe code in C++ and what are the exception safety guarantees?',
        'Explain template metaprogramming with a practical example from your experience.',
        'How do you profile and optimize C++ code for performance-critical applications?',
        'Describe how you handle cross-platform compilation and build system management (CMake, Makefile).',
        'How do you implement design patterns like CRTP, Pimpl, or Observer in modern C++?',
    ],
    'mern-stack': [
        'Design the full architecture for a MERN-based e-commerce platform with user authentication and payments.',
        'How do you structure a MongoDB schema for a social media application with posts, comments, and likes?',
        'Explain how you handle authentication in a MERN stack using JWT, refresh tokens, and httpOnly cookies.',
        'How do you implement real-time features in a MERN app using Socket.io?',
        'Describe your approach to state management in React when working with a MongoDB/Express backend.',
        'How do you implement file upload and image handling across the MERN stack?',
        'Walk me through how you deploy a MERN application with Docker and set up CI/CD.',
        'How do you handle API error responses in Express and display them gracefully in React?',
        'Explain MongoDB aggregation pipelines with a real use case you have implemented.',
        'How do you implement pagination, filtering, and search across a MERN stack application?',
        'Describe your testing strategy for a MERN app covering unit, integration, and end-to-end tests.',
        'How do you optimize a slow MERN application? Cover both frontend and backend bottlenecks.',
    ],
    'ai-engineer': [
        'Explain the bias-variance tradeoff and how it affects model selection in machine learning.',
        'How do you design a complete ML pipeline from data collection to model deployment and monitoring?',
        'Describe the differences between CNNs, RNNs, and Transformers. When would you use each architecture?',
        'How do you handle class imbalance in a classification problem? Compare at least three techniques.',
        'Walk me through how you would deploy a trained model as a REST API with proper scaling.',
        'Explain transfer learning and fine-tuning with a real project example.',
        'How do you evaluate model performance beyond accuracy? Discuss precision, recall, F1, and AUC-ROC.',
        'Describe your approach to feature engineering and feature selection for tabular data.',
        'How do you handle large-scale training with distributed computing or GPU clusters?',
        'Explain how you implement model versioning, experiment tracking, and reproducibility (MLflow, DVC).',
        'How do you detect and mitigate model drift in production?',
        'Describe your experience with NLP tasks like text classification, NER, or language generation.',
    ],
    'data-analyst': [
        'How do you approach a new dataset? Walk me through your exploratory data analysis workflow.',
        'Explain how you write complex SQL queries involving window functions, CTEs, and subqueries.',
        'How do you clean and handle missing data, outliers, and inconsistent formats in a dataset?',
        'Describe how you build interactive dashboards in Tableau or Power BI for business stakeholders.',
        'How do you choose the right visualization type for different kinds of data and audiences?',
        'Walk me through a project where your data analysis directly influenced a business decision.',
        'How do you perform A/B test analysis and determine statistical significance?',
        'Explain your approach to writing automated reports and data pipelines using Python or SQL.',
        'How do you ensure data quality and integrity in the reports you produce?',
        'Describe how you handle large datasets that don\'t fit in memory using tools like chunking or databases.',
        'How do you communicate technical findings to non-technical stakeholders effectively?',
        'Explain cohort analysis, funnel analysis, or customer segmentation with a practical example.',
    ],
    'devops-engineer': [
        'Design a CI/CD pipeline for a microservices application. Cover build, test, and deployment stages.',
        'How do you implement Infrastructure as Code using Terraform? Describe your state management approach.',
        'Explain Kubernetes architecture and how you deploy and scale applications using it.',
        'How do you implement monitoring and alerting using tools like Prometheus, Grafana, and ELK stack?',
        'Describe your approach to container security scanning and secure Docker image builds.',
        'How do you handle secrets management in a DevOps pipeline (HashiCorp Vault, AWS Secrets Manager)?',
        'Walk me through a blue-green or canary deployment strategy you have implemented.',
        'How do you implement log aggregation and centralized logging for distributed systems?',
        'Explain how you manage multiple environments (dev, staging, prod) with consistent configurations.',
        'How do you handle disaster recovery and backup strategies for cloud infrastructure?',
        'Describe your approach to automating server provisioning and configuration with Ansible.',
        'How do you implement network security (VPCs, security groups, firewalls) in a cloud environment?',
    ],
    'javascript-developer': [
        'Explain closures in JavaScript with a practical example of where they solve real problems.',
        'How does the JavaScript event loop work? Explain the call stack, callback queue, and microtask queue.',
        'Describe the differences between var, let, and const, and how hoisting affects each.',
        'How do you handle asynchronous code using Promises, async/await, and error handling patterns?',
        'Explain prototypal inheritance in JavaScript and how it differs from classical inheritance.',
        'How do you use ES6+ features (destructuring, spread, modules, generators) in production code?',
        'Describe your approach to module bundling with Webpack, including code splitting and optimization.',
        'How do you write effective unit tests for JavaScript using Jest or Mocha?',
        'Explain the concept of immutability in JavaScript and why it matters for state management.',
        'How do you handle memory leaks in JavaScript applications and what tools do you use to detect them?',
        'Describe your approach to error handling and logging in a JavaScript application.',
        'How do you optimize JavaScript performance including debouncing, throttling, and lazy evaluation?',
    ],
    'react-developer': [
        'Explain the React component lifecycle and how hooks (useEffect, useMemo, useCallback) map to lifecycle phases.',
        'How do you decide between Context API, Redux, Zustand, or other state management solutions?',
        'Describe how you implement code splitting and lazy loading in a React application.',
        'How do you write reusable custom hooks? Give an example from a real project.',
        'Explain how React reconciliation works and what causes unnecessary re-renders.',
        'How do you handle forms in React? Compare controlled components, React Hook Form, and Formik.',
        'Describe your testing strategy for React components using React Testing Library.',
        'How do you implement server-side rendering with Next.js and when is it the right choice?',
        'Explain how you handle routing, nested routes, and route guards in a React SPA.',
        'How do you optimize a React application that has performance issues with large lists or frequent updates?',
        'Describe how you implement error boundaries and global error handling in React.',
        'How do you manage side effects and data fetching patterns (SWR, React Query) in React?',
    ],
    'mean-stack': [
        'Design the architecture for a MEAN-based project management tool with real-time updates.',
        'How does Angular\'s dependency injection system work and why is it central to the framework?',
        'Explain RxJS observables and how you use them for handling async operations in Angular.',
        'How do you implement authentication with Angular guards, interceptors, and Express middleware?',
        'Describe your approach to structuring Angular modules, components, and services in a large application.',
        'How do you handle MongoDB schema design with references versus embedded documents in a MEAN app?',
        'Walk me through how you implement form handling in Angular using reactive forms and validation.',
        'How do you implement server-side pagination and filtering with Express and MongoDB aggregation?',
        'Describe your deployment and environment management strategy for a MEAN stack application.',
        'How do you handle error logging and monitoring across Angular frontend and Express backend?',
        'Explain Angular change detection strategies and how you optimize rendering performance.',
        'How do you implement role-based access control across the entire MEAN stack?',
    ],
    'nodejs-developer': [
        'Explain the Node.js event-driven architecture and how the libuv event loop manages I/O operations.',
        'How do you handle error management in Express.js including async errors and middleware error handlers?',
        'Describe your approach to building a scalable REST API with proper validation and documentation.',
        'How do you implement WebSocket communication in Node.js for real-time features?',
        'Explain how you handle process management, clustering, and load balancing in Node.js production apps.',
        'How do you implement authentication middleware with JWT verification and refresh token rotation?',
        'Describe your database access patterns in Node.js using Mongoose, Sequelize, or Prisma.',
        'How do you handle file streaming and large file processing in Node.js without memory issues?',
        'Walk me through how you implement message queues (RabbitMQ, Bull) for background task processing.',
        'How do you write integration tests for Express APIs using Supertest and test databases?',
        'Explain how you manage environment variables, configuration, and secrets in a Node.js application.',
        'How do you profile and debug performance issues in a Node.js application?',
    ],
    'data-scientist': [
        'Walk me through your end-to-end workflow for a data science project from problem definition to deployment.',
        'How do you handle feature engineering for a predictive modeling task? Give a specific example.',
        'Explain the differences between supervised, unsupervised, and reinforcement learning with use cases.',
        'How do you select and tune hyperparameters for a machine learning model?',
        'Describe your approach to cross-validation and preventing data leakage.',
        'How do you communicate model results and uncertainty to business stakeholders?',
        'Explain dimensionality reduction techniques (PCA, t-SNE, UMAP) and when to use each.',
        'How do you handle time series forecasting including stationarity, seasonality, and model selection?',
        'Describe your experience with deep learning frameworks and when you choose deep learning over traditional ML.',
        'How do you set up reproducible experiments with version control for data, code, and models?',
        'Explain how you evaluate and compare multiple models for a classification or regression task.',
        'How do you handle ethical considerations and bias in data science projects?',
    ],
    'data-engineer': [
        'Design a data pipeline that ingests data from multiple sources, transforms it, and loads it into a warehouse.',
        'Explain the differences between batch processing and stream processing. When do you use each?',
        'How do you implement data quality checks and monitoring in a production ETL pipeline?',
        'Describe your experience with Apache Spark for large-scale data processing.',
        'How do you design a data warehouse schema (star schema vs snowflake schema)?',
        'Walk me through how you handle schema evolution and backward compatibility in data pipelines.',
        'How do you implement data partitioning and indexing strategies for query performance?',
        'Explain how you use Airflow or similar tools for workflow orchestration and scheduling.',
        'How do you handle data deduplication and exactly-once processing in distributed systems?',
        'Describe your approach to data lake architecture and catalog management.',
        'How do you implement change data capture (CDC) for real-time data synchronization?',
        'Explain how you handle security, access control, and compliance in data engineering workflows.',
    ],
    'cloud-engineer': [
        'Design a highly available and fault-tolerant cloud architecture for a web application.',
        'How do you implement auto-scaling policies and right-size cloud resources for cost optimization?',
        'Explain how you manage IAM roles, policies, and least-privilege access in AWS or Azure.',
        'How do you implement a multi-region deployment strategy with data replication?',
        'Describe your approach to cloud cost monitoring, budgeting, and FinOps practices.',
        'How do you design and implement serverless architectures using Lambda, API Gateway, or Azure Functions?',
        'Walk me through how you set up VPC networking, subnets, and security groups for a production workload.',
        'How do you implement cloud-native CI/CD pipelines with infrastructure testing?',
        'Explain your disaster recovery and business continuity strategy for cloud-hosted applications.',
        'How do you handle cloud migration from on-premises infrastructure? Describe your assessment approach.',
        'Describe how you implement container orchestration on cloud platforms (EKS, AKS, GKE).',
        'How do you implement logging, monitoring, and observability using cloud-native tools?',
    ],
    'mobile-developer': [
        'How do you decide between native development and cross-platform frameworks for a mobile project?',
        'Describe your approach to handling different screen sizes, orientations, and device capabilities.',
        'How do you implement offline-first functionality with local storage and data synchronization?',
        'Explain how you handle push notifications across iOS and Android platforms.',
        'How do you optimize mobile app performance including startup time, memory usage, and battery consumption?',
        'Describe your approach to mobile app security including secure storage, SSL pinning, and code obfuscation.',
        'How do you implement CI/CD for mobile apps including automated testing and app store deployment?',
        'Walk me through how you handle deep linking and universal links in a mobile application.',
        'How do you implement state management and navigation patterns in a mobile app?',
        'Describe your approach to writing unit tests and UI tests for mobile applications.',
        'How do you handle REST API integration, caching, and error handling in a mobile app?',
        'Explain how you manage app versioning, feature flags, and phased rollouts.',
    ],
    'flutter-developer': [
        'Explain the Flutter widget tree, element tree, and render tree. How do they work together?',
        'How do you choose between BLoC, Provider, Riverpod, and GetX for state management in Flutter?',
        'Describe how you build responsive layouts in Flutter that work across mobile, tablet, and web.',
        'How do you implement platform-specific features and native code integration using platform channels?',
        'Walk me through how you handle navigation and routing in a large Flutter application.',
        'How do you optimize Flutter app performance including widget rebuilds and rendering?',
        'Describe your approach to writing widget tests, integration tests, and golden tests in Flutter.',
        'How do you implement local data persistence in Flutter using Hive, sqflite, or shared preferences?',
        'Explain how you handle theming, dark mode, and dynamic styling in a Flutter application.',
        'How do you implement authentication flows including social login in a Flutter app?',
        'Describe your approach to handling animations and custom painters in Flutter.',
        'How do you set up CI/CD for Flutter apps and manage separate builds for iOS and Android?',
    ],
    'android-developer': [
        'Explain the Android activity lifecycle and how you handle configuration changes properly.',
        'How do you implement the MVVM architecture pattern using ViewModel, LiveData, and Repository?',
        'Describe your experience with Jetpack Compose and how it compares to XML-based layouts.',
        'How do you handle background work in Android using WorkManager, coroutines, and services?',
        'Walk me through how you implement Room database with migrations and complex queries.',
        'How do you handle dependency injection in Android using Hilt or Dagger?',
        'Describe your approach to implementing network calls with Retrofit, handling errors and caching.',
        'How do you optimize Android app performance including layout rendering and memory management?',
        'Explain how you implement navigation using Navigation Component with Safe Args.',
        'How do you handle permissions, camera, location, and other system services in Android?',
        'Describe your testing strategy for Android apps including unit tests, instrumented tests, and Espresso.',
        'How do you implement push notifications and Firebase Cloud Messaging in an Android app?',
    ],
    'ios-developer': [
        'Explain the iOS app lifecycle and how you handle state transitions and background execution.',
        'How do you implement the MVVM pattern in Swift with Combine or async/await?',
        'Describe how you build modern UIs with SwiftUI and when you choose UIKit instead.',
        'How do you manage data persistence using Core Data, including migrations and relationships?',
        'Walk me through how you implement networking with URLSession and Codable for JSON parsing.',
        'How do you handle memory management in Swift including ARC, retain cycles, and weak references?',
        'Describe your approach to dependency management using Swift Package Manager or CocoaPods.',
        'How do you implement push notifications and handle notification payloads in an iOS app?',
        'Explain how you use Combine framework for reactive programming and data binding.',
        'How do you optimize iOS app performance including launch time, scrolling, and memory usage?',
        'Describe your testing strategy using XCTest for unit tests and XCUITest for UI tests.',
        'How do you handle App Store submission, code signing, provisioning profiles, and TestFlight distribution?',
    ],
    'blockchain-developer': [
        'Explain how Ethereum smart contracts work and the lifecycle of a transaction on the blockchain.',
        'How do you write secure Solidity code and prevent common vulnerabilities like reentrancy attacks?',
        'Describe the difference between proof-of-work and proof-of-stake consensus mechanisms.',
        'How do you implement ERC-20 and ERC-721 token standards? Explain the key functions.',
        'Walk me through how you test and deploy smart contracts using Hardhat or Truffle.',
        'How do you interact with smart contracts from a frontend using Web3.js or Ethers.js?',
        'Describe your approach to gas optimization in Solidity smart contracts.',
        'How do you implement decentralized storage using IPFS and integrate it with blockchain applications?',
        'Explain the differences between Layer 1 and Layer 2 scaling solutions.',
        'How do you implement a DeFi protocol (lending, swapping, or staking)?',
        'Describe your approach to smart contract auditing and security analysis.',
        'How do you handle upgradeability in smart contracts using proxy patterns?',
    ],
    'cybersecurity-engineer': [
        'Describe your methodology for conducting a penetration test on a web application.',
        'How do you implement a Security Information and Event Management (SIEM) system for threat detection?',
        'Explain the OWASP Top 10 vulnerabilities and how you mitigate each in a production application.',
        'How do you design and implement an incident response plan for a security breach?',
        'Walk me through how you perform vulnerability assessment and risk scoring for an organization.',
        'How do you implement network security monitoring using tools like Wireshark, Snort, or Suricata?',
        'Describe your approach to implementing zero-trust architecture.',
        'How do you handle identity and access management (IAM) including MFA and SSO?',
        'Explain how encryption (symmetric, asymmetric, hashing) is applied in different security scenarios.',
        'How do you implement secure coding practices and integrate security into CI/CD (DevSecOps)?',
        'Describe your experience with cloud security controls and compliance frameworks (SOC2, HIPAA, PCI-DSS).',
        'How do you perform threat modeling and create security architecture for a new application?',
    ],
}


@interview_bp.route('/interview')
def interview():
    return render_template('interview.html')


@interview_bp.route('/interview/report')
def interview_report():
    interview_state = session.get('interview', {})
    if not interview_state or interview_state.get('status') != 'completed':
        flash('Complete an interview session first to view the report.', 'warning')
        return redirect(url_for('interview.interview'))

    report = interview_state.get('report') or _build_report_from_answers(
        interview_state.get('answers', []),
        interview_state.get('role', 'web-developer'),
        interview_state.get('resume_context', {}),
        elapsed_seconds=_compute_elapsed(interview_state),
    )
    return render_template('report_interview.html', report=report)


@interview_bp.route('/interview/report/<int:session_id>')
def view_interview_report(session_id):
    if not current_user.is_authenticated:
        flash('Please login to access saved interview reports.', 'warning')
        return redirect(url_for('auth.login'))

    db_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not db_session:
        flash('Interview report not found.', 'error')
        return redirect(url_for('dashboard.history'))

    responses = InterviewResponse.query.filter_by(session_id=session_id).order_by(InterviewResponse.created_at.asc()).all()
    answer_rows = [
        {
            'question': item.question_text,
            'category': item.category,
            'answer': item.answer_text or '',
            'answer_mode': item.answer_mode,
            'score': float(item.logic_score or 0),
            'feedback': item.feedback or '',
        }
        for item in responses
    ]

    role_slug = _slugify_role(db_session.role)
    report = _build_report_from_answers(
        answer_rows,
        role_slug,
        resume_context={},
        elapsed_seconds=0,
    )
    report['generated_at'] = db_session.created_at.strftime('%Y-%m-%d %H:%M') if db_session.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    report['session_status'] = db_session.status

    return render_template('report_interview.html', report=report)


@interview_bp.route('/interview/report/download')
def download_interview_report():
    interview_state = session.get('interview', {})
    if not interview_state or interview_state.get('status') != 'completed':
        flash('No completed interview found. Complete an interview session first.', 'warning')
        return redirect(url_for('interview.interview'))

    report = interview_state.get('report', {})
    if not report:
        flash('Unable to generate report.', 'error')
        return redirect(url_for('interview.interview_report'))

    candidate_name = current_user.name if current_user.is_authenticated else 'Candidate'
    role = report.get('role', 'Tech Role')
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    report_filename = f"interview-{candidate_name.replace(' ', '_')}-{role.replace(' ', '_')}.pdf"
    report_path = os.path.join(REPORT_FOLDER, report_filename)

    generate_interview_report_pdf(report_path, report, candidate_name)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_filename,
    )


@interview_bp.route('/interview/report/<int:session_id>/download')
@interview_bp.route('/history/interview/<int:session_id>/download')
def download_interview_history(session_id):
    if not current_user.is_authenticated:
        flash('Please login to download interview reports.', 'warning')
        return redirect(url_for('auth.login'))

    db_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not db_session:
        flash('Interview report not found.', 'error')
        return redirect(url_for('dashboard.history'))

    responses = InterviewResponse.query.filter_by(session_id=session_id).order_by(InterviewResponse.created_at.asc()).all()
    answer_rows = [
        {
            'question': item.question_text,
            'category': item.category,
            'answer': item.answer_text or '',
            'answer_mode': item.answer_mode,
            'score': float(item.logic_score or 0),
            'feedback': item.feedback or '',
        }
        for item in responses
    ]

    role_slug = _slugify_role(db_session.role)
    report = _build_report_from_answers(
        answer_rows,
        role_slug,
        resume_context={},
        elapsed_seconds=0,
    )
    report['generated_at'] = db_session.created_at.strftime('%Y-%m-%d %H:%M') if db_session.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')

    candidate_name = current_user.name if current_user.is_authenticated else 'Candidate'
    role = db_session.role

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    REPORT_FOLDER = os.path.join(BASE_DIR, 'uploads', 'reports')
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    report_filename = f"interview-{session_id}-{candidate_name.replace(' ', '_')}-{role.replace(' ', '_')}.pdf"
    report_path = os.path.join(REPORT_FOLDER, report_filename)

    generate_interview_report_pdf(report_path, report, candidate_name)

    return send_file(
        report_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_filename,
    )


@interview_bp.route('/api/interview/get_resumes', methods=['POST'])
def get_available_resumes():
    """Fetch available analyzed resumes for the selected role."""
    if not current_user.is_authenticated:
        return jsonify({'resumes': []})
    
    payload = request.get_json(silent=True) or {}
    role_slug = payload.get('job_role', 'web-developer')
    role_title = role_slug.replace('-', ' ').title()
    
    resumes = Resume.query.filter_by(
        user_id=current_user.id,
        role_target=role_title
    ).order_by(Resume.created_at.desc()).limit(5).all()
    
    resume_list = [{
        'id': r.id,
        'filename': r.filename,
        'ats_score': r.ats_score or 0,
        'created_at': r.created_at.strftime('%b %d, %Y'),
    } for r in resumes]
    
    return jsonify({'resumes': resume_list})


@interview_bp.route('/api/interview/start', methods=['POST'])
def start_interview():
    # Handle both JSON and form data (for file upload)
    if request.is_json:
        role_slug = request.json.get('job_role', 'web-developer')
        resume_file = None
        existing_resume_id = request.json.get('existing_resume_id')
    else:
        role_slug = request.form.get('job_role', 'web-developer')
        resume_file = request.files.get('resume_file')
        existing_resume_id = request.form.get('existing_resume_id')

    # Parse resume if provided
    resume_data = None
    resume_source = None
    
    # Priority: uploaded file > existing resume selection
    if resume_file and resume_file.filename:
        try:
            resume_text = _extract_resume_text(resume_file)
            if resume_text:
                resume_data = parse_resume_for_interview(resume_text, role_slug)
                resume_source = 'uploaded'
        except Exception as e:
            pass  # Continue without resume-based questions if parsing fails
    elif existing_resume_id and current_user.is_authenticated:
        try:
            existing_resume = Resume.query.get(int(existing_resume_id))
            if existing_resume and existing_resume.user_id == current_user.id:
                # Read the stored resume file
                import os
                if os.path.exists(existing_resume.file_path):
                    with open(existing_resume.file_path, 'rb') as f:
                        resume_text = _extract_resume_text(f)
                        if resume_text:
                            resume_data = parse_resume_for_interview(resume_text, role_slug)
                            resume_source = 'reused'
        except Exception as e:
            pass  # Continue without resume-based questions if parsing fails

    # Determine difficulty level
    difficulty = 'advanced' if resume_data else 'standard'
    
    _seed_question_bank_for_role(role_slug, resume_data=resume_data, difficulty=difficulty)

    questions = InterviewQuestion.query.filter_by(
        role_slug=role_slug,
        is_active=True,
    ).order_by(InterviewQuestion.order_index.asc()).all()

    if len(questions) < 15:
        return jsonify({'error': 'Not enough questions available for this role. Please try again.'}), 400

    resume_context = _get_resume_context(role_slug)

    db_session_id = None
    if current_user.is_authenticated:
        try:
            interview_session = InterviewSession(
                user_id=current_user.id,
                role=role_slug.replace('-', ' ').title(),
                status='active',
                created_at=datetime.utcnow(),
            )
            db.session.add(interview_session)
            db.session.commit()
            db_session_id = interview_session.id
        except Exception:
            db.session.rollback()

    first_question = _serialize_question(questions[0], index=1, total=len(questions))

    session['interview'] = {
        'role': role_slug,
        'question_ids': [item.id for item in questions],
        'current_index': 0,
        'answers': [],
        'status': 'active',
        'start_time': time.time(),
        'end_time': None,
        'db_session_id': db_session_id,
        'resume_context': resume_context,
        'resume_uploaded': resume_data is not None,
        'resume_source': resume_source,
        'difficulty': difficulty,
    }

    return jsonify({
        'ok': True,
        'question': first_question,
        'total_questions': len(questions),
        'resume_context_used': bool(resume_context.get('has_analysis')),
        'resume_uploaded': resume_data is not None,
        'resume_source': resume_source,
        'difficulty': difficulty,
    })


@interview_bp.route('/api/interview/current', methods=['GET'])
def current_question():
    interview_state = session.get('interview', {})
    if interview_state.get('status') != 'active':
        return jsonify({'error': 'No active interview session found.'}), 400

    question_data = _get_current_question(interview_state)
    if not question_data:
        return jsonify({'complete': True})

    return jsonify({'ok': True, 'question': question_data})


@interview_bp.route('/api/interview/answer', methods=['POST'])
def submit_answer():
    interview_state = session.get('interview', {})
    if interview_state.get('status') != 'active':
        return jsonify({'error': 'No active interview session found.'}), 400

    payload = request.get_json(silent=True) or {}
    answer_text = (payload.get('answer') or '').strip()
    answer_mode = (payload.get('answer_mode') or 'text').strip().lower()
    response_seconds = int(payload.get('response_seconds') or 0)

    if answer_mode not in {'text', 'oral'}:
        answer_mode = 'text'

    if not answer_text:
        return jsonify({'error': 'Please provide an answer before moving to the next question.'}), 400

    question_ids = interview_state.get('question_ids', [])
    current_index = interview_state.get('current_index', 0)
    if current_index >= len(question_ids):
        _complete_interview(interview_state)
        session['interview'] = interview_state
        return jsonify({'complete': True, 'redirect_url': url_for('interview.interview_report')})

    question_obj = InterviewQuestion.query.get(question_ids[current_index])
    if not question_obj:
        return jsonify({'error': 'Current question not found.'}), 404

    role_slug = interview_state.get('role', 'web-developer')
    score, feedback = _score_answer(
        answer_text=answer_text,
        category=question_obj.category,
        role_slug=role_slug,
    )

    answer_row = {
        'question': question_obj.question_text,
        'category': question_obj.category,
        'answer': answer_text,
        'answer_mode': answer_mode,
        'score': score,
        'feedback': feedback,
    }
    interview_state.setdefault('answers', []).append(answer_row)

    db_session_id = interview_state.get('db_session_id')
    if db_session_id:
        try:
            db_answer = InterviewResponse(
                session_id=db_session_id,
                question_id=question_obj.id,
                question_text=question_obj.question_text,
                category=question_obj.category,
                answer_mode=answer_mode,
                answer_text=answer_text,
                response_seconds=response_seconds,
                logic_score=score,
                feedback=feedback,
                created_at=datetime.utcnow(),
            )
            db.session.add(db_answer)
            db.session.commit()
        except Exception:
            db.session.rollback()

    interview_state['current_index'] = current_index + 1

    if interview_state['current_index'] >= len(question_ids):
        _complete_interview(interview_state)
        session['interview'] = interview_state
        return jsonify({
            'complete': True,
            'report': interview_state.get('report', {}),
            'redirect_url': url_for('interview.interview_report'),
        })

    session['interview'] = interview_state
    next_q = _get_current_question(interview_state)
    return jsonify({
        'ok': True,
        'question': next_q,
        'last_score': score,
        'last_feedback': feedback,
    })


@interview_bp.route('/api/interview/end', methods=['POST'])
def end_interview():
    interview_state = session.get('interview', {})
    if not interview_state:
        return jsonify({'error': 'No interview session found.'}), 400

    _complete_interview(interview_state)
    session['interview'] = interview_state

    return jsonify({
        'ok': True,
        'report': interview_state.get('report', {}),
        'redirect_url': url_for('interview.interview_report'),
    })


def _serialize_question(question_obj, index: int, total: int):
    return {
        'id': question_obj.id,
        'text': question_obj.question_text,
        'category': question_obj.category,
        'round_label': ROUND_LABELS.get(question_obj.category, question_obj.category.title()),
        'index': index,
        'total': total,
    }


def _get_current_question(interview_state):
    question_ids = interview_state.get('question_ids', [])
    current_index = interview_state.get('current_index', 0)
    if current_index >= len(question_ids):
        return None

    question_obj = InterviewQuestion.query.get(question_ids[current_index])
    if not question_obj:
        return None

    return _serialize_question(question_obj, index=current_index + 1, total=len(question_ids))


def _slugify_role(role_name: str):
    return (role_name or '').strip().lower().replace(' ', '-')


def _seed_question_bank_for_role(role_slug: str, resume_data: dict = None, difficulty: str = 'standard'):
    existing_count = InterviewQuestion.query.filter_by(role_slug=role_slug, is_active=True).count()
    if existing_count >= 15:
        return

    # Combine base + extended questions for 24 total, then randomly select 12
    base_questions = ROLE_QUESTIONS.get(role_slug, [])
    extended_questions = EXTENDED_ROLE_QUESTIONS.get(role_slug, [])
    all_technical = base_questions + extended_questions

    # For advanced difficulty (resume-based), favor extended questions (harder)
    if difficulty == 'advanced' and len(base_questions) >= 6 and len(extended_questions) >= 6:
        # 40% from base (easier), 60% from extended (harder)
        base_count = 5
        extended_count = 7
        technical_questions = (
            random.sample(base_questions, min(base_count, len(base_questions))) +
            random.sample(extended_questions, min(extended_count, len(extended_questions)))
        )
        random.shuffle(technical_questions)
    elif len(all_technical) >= 12:
        # Standard difficulty: evenly distributed
        technical_questions = random.sample(all_technical, min(12, len(all_technical)))
    elif len(all_technical) > 0:
        technical_questions = all_technical[:12]
    else:
        # Fallback to keyword-based generation
        role_keywords = TECH_ROLE_KEYWORDS.get(role_slug, TECH_ROLE_KEYWORDS.get('web-developer', []))
        technical_questions = []
        for idx, keyword in enumerate(role_keywords[:10]):
            template = TECHNICAL_PROMPTS[idx % len(TECHNICAL_PROMPTS)]
            technical_questions.append(template.format(keyword=keyword))
        technical_questions.extend([
            'Explain your approach to writing maintainable and readable code under deadlines.',
            'How do you troubleshoot production bugs when logs are incomplete?',
        ])
        technical_questions = technical_questions[:12]

    # If resume data provided, replace some technical questions with resume-specific ones
    if resume_data and resume_data.get('resume_questions'):
        resume_questions = resume_data['resume_questions']
        # Use more resume questions for advanced difficulty
        num_resume_q = min(6 if difficulty == 'advanced' else 4, len(resume_questions))
        if num_resume_q > 0:
            # Replace last N technical questions with resume-based ones
            technical_questions = technical_questions[:-num_resume_q]
            for rq in resume_questions[:num_resume_q]:
                technical_questions.append(rq['question_text'])
            random.shuffle(technical_questions)  # Mix them in

    ordered_questions = []
    for item in INTRO_QUESTIONS[:5]:
        ordered_questions.append({'category': 'intro', 'question_text': item, 'difficulty': 'easy'})

    for item in technical_questions:
        ordered_questions.append({'category': 'technical', 'question_text': item, 'difficulty': 'medium'})

    for item in PRESSURE_QUESTIONS:
        ordered_questions.append({'category': 'pressure', 'question_text': item, 'difficulty': 'hard'})

    if existing_count > 0:
        InterviewQuestion.query.filter_by(role_slug=role_slug).delete()
        db.session.commit()

    for order_index, row in enumerate(ordered_questions, start=1):
        db.session.add(InterviewQuestion(
            role_slug=role_slug,
            category=row['category'],
            question_text=row['question_text'],
            difficulty=row['difficulty'],
            order_index=order_index,
            is_active=True,
            created_at=datetime.utcnow(),
        ))

    db.session.commit()


def _extract_resume_text(resume_file):
    """Extract text from uploaded PDF resume file."""
    try:
        with pdfplumber.open(resume_file) as pdf:
            text = ''
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
            return text.strip()
    except Exception as e:
        return None


def _get_resume_context(role_slug: str):
    context = {
        'has_analysis': False,
        'ats_score': 0,
        'missing_keywords': [],
        'weak_points': [],
    }

    if not current_user.is_authenticated:
        return context

    role_title = role_slug.replace('-', ' ').title()
    resume = Resume.query.filter_by(user_id=current_user.id, role_target=role_title).order_by(Resume.created_at.desc()).first()
    if not resume:
        return context

    try:
        analysis = json.loads(resume.analysis) if resume.analysis else {}
    except Exception:
        analysis = {}

    if not analysis:
        return context

    context['has_analysis'] = True
    context['ats_score'] = analysis.get('ats_score', resume.ats_score or 0)
    context['missing_keywords'] = analysis.get('missing_keywords', [])[:6]
    context['weak_points'] = analysis.get('weak_points', [])[:4]
    return context


def _score_answer(answer_text: str, category: str, role_slug: str):
    text = answer_text.lower()
    words = [token for token in text.split() if token.strip()]
    word_count = len(words)

    base_score = min(45, word_count * 1.5)

    structure_bonus = 0
    for marker in ['because', 'therefore', 'for example', 'result', 'impact']:
        if marker in text:
            structure_bonus += 5
    structure_bonus = min(structure_bonus, 20)

    keyword_bonus = 0
    if category == 'technical':
        role_keywords = TECH_ROLE_KEYWORDS.get(role_slug, [])
        matched = [kw for kw in role_keywords if kw.lower() in text]
        keyword_bonus = min(len(matched) * 6, 25)

    pressure_bonus = 0
    if category == 'pressure':
        for token in ['prioritize', 'communicate', 'risk', 'rollback', 'stakeholder', 'tradeoff']:
            if token in text:
                pressure_bonus += 4
        pressure_bonus = min(pressure_bonus, 20)

    final_score = min(round(base_score + structure_bonus + keyword_bonus + pressure_bonus, 1), 100.0)

    if final_score >= 80:
        feedback = 'Strong answer with clear structure and practical thinking.'
    elif final_score >= 65:
        feedback = 'Good answer. Add more specific examples and measurable outcomes.'
    elif final_score >= 45:
        feedback = 'Average answer. Improve depth, structure, and technical precision.'
    else:
        feedback = 'Needs improvement. Use a clearer framework and concrete examples.'

    return final_score, feedback


def _compute_elapsed(interview_state):
    start_time = interview_state.get('start_time')
    end_time = interview_state.get('end_time')
    if not start_time:
        return 0
    if not end_time:
        end_time = time.time()
    return max(0, int(end_time - start_time))


def _complete_interview(interview_state):
    if interview_state.get('status') == 'completed':
        return

    interview_state['status'] = 'completed'
    interview_state['end_time'] = time.time()
    report = _build_report_from_answers(
        interview_state.get('answers', []),
        interview_state.get('role', 'web-developer'),
        interview_state.get('resume_context', {}),
        elapsed_seconds=_compute_elapsed(interview_state),
    )
    interview_state['report'] = report

    db_session_id = interview_state.get('db_session_id')
    if db_session_id:
        try:
            db_row = InterviewSession.query.get(db_session_id)
            if db_row:
                db_row.status = 'completed'
                db_row.overall_score = report.get('overall_score', 0)
                db.session.commit()
        except Exception:
            db.session.rollback()


def _build_report_from_answers(answers, role_slug, resume_context, elapsed_seconds=0):
    intro_scores = [item['score'] for item in answers if item.get('category') == 'intro']
    technical_scores = [item['score'] for item in answers if item.get('category') == 'technical']
    pressure_scores = [item['score'] for item in answers if item.get('category') == 'pressure']

    intro_avg = round(mean(intro_scores), 1) if intro_scores else 0.0
    technical_avg = round(mean(technical_scores), 1) if technical_scores else 0.0
    pressure_avg = round(mean(pressure_scores), 1) if pressure_scores else 0.0

    all_scores = [item.get('score', 0) for item in answers]
    overall = round(mean(all_scores), 1) if all_scores else 0.0

    strengths = []
    improvements = []

    if intro_avg >= 75:
        strengths.append('Your self-introduction and communication clarity are strong.')
    else:
        improvements.append('Refine your 60-second introduction using role relevance and outcomes.')

    if technical_avg >= 75:
        strengths.append('Technical explanations showed good depth and practical understanding.')
    else:
        improvements.append('Increase technical depth with architecture decisions, tradeoffs, and metrics.')

    if pressure_avg >= 70:
        strengths.append('Pressure-handling responses showed calm prioritization and communication.')
    else:
        improvements.append('Use structured incident response: assess risk, communicate, prioritize, then execute.')

    if resume_context.get('has_analysis'):
        strengths.append('Resume analysis context was reused to avoid re-processing profile basics.')
        missing = resume_context.get('missing_keywords', [])
        if missing:
            improvements.append('Practice answers that naturally include missing keywords: ' + ', '.join(missing[:4]) + '.')

    if not strengths:
        strengths.append('You completed a full mock interview session and captured answer history for review.')

    if not improvements:
        improvements.append('Keep practicing concise STAR-style answers and quantify outcomes where possible.')

    recommendations = [
        'Use the STAR format (Situation, Task, Action, Result) for scenario and pressure questions.',
        'Add one concrete project example in every technical answer.',
        'Limit each answer to 60-120 seconds with clear structure.',
        'Track weak questions and repeat them in your next mock session.',
    ]

    detailed_feedback = []
    for idx, item in enumerate(answers, start=1):
        detailed_feedback.append({
            'index': idx,
            'category': item.get('category', 'technical'),
            'question': item.get('question', ''),
            'answer_mode': item.get('answer_mode', 'text'),
            'score': item.get('score', 0),
            'feedback': item.get('feedback', ''),
        })

    return {
        'generated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        'role': role_slug.replace('-', ' ').title(),
        'total_questions': len(answers),
        'duration_minutes': round(elapsed_seconds / 60.0, 1) if elapsed_seconds else 0,
        'overall_score': overall,
        'intro_score': intro_avg,
        'technical_score': technical_avg,
        'pressure_score': pressure_avg,
        'resume_context_used': bool(resume_context.get('has_analysis')),
        'resume_ats_score': resume_context.get('ats_score', 0),
        'strengths': strengths,
        'improvements': improvements,
        'recommendations': recommendations,
        'detailed_feedback': detailed_feedback,
    }
