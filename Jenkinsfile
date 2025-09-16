pipeline {
    agent {
        dockerfile {
            filename 'Dockerfile'
            args '--network=mssql_mssql_default'
        }
    }

    environment {
        DB_HOST     = 'mssql_uat'
        DB_USER     = 'sa'
        DB_PASSWORD = 'StrongPassword123**'
        DB_NAME     = 'test'
        DB_PORT     = '1433'
    }
    
    stages {
        stage('Run Deployment Script') {
            when {
                // allOf {
                    // expression { env.CHANGE_ID == null } // ensures this is not a PR build
                    // branch 'main'                       // run only after PR is merged into main
                // }
                branch 'main'  
            }
            steps {
                withEnv([
                    "DB_SERVER=${env.DB_HOST}",
                    "DB_USERNAME=${env.DB_USER}",
                    "DB_PASSWORD=${env.DB_PASSWORD}",
                    "DB_DATABASE=${env.DB_NAME}",
                    "DB_PORT=${env.DB_PORT}"
                ]) {
                    sh """
                    python deploy.py
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Successfully deployed after PR merge to main."
        }
        failure {
            echo "❌ Deployment failed."
        }
    }
}
