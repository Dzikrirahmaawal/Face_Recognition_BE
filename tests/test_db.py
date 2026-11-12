import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
e = create_engine("mssql+pyodbc://sa:Aa9!I-buwH2l8vgjIqq9Lj_fRXofnu146E_D@localhost:1433/visitor_attendance?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes")
with e.connect() as c:
    print("DB OK:", c.execute(text("select 1")).scalar())