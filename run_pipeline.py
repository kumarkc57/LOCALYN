import sys
from backend.app.ingestion.pipeline import run_ingestion_pipeline
from backend.app.database.db import get_reports, count_reports

def main():
    print("=" * 60)
    print("LOCALYN — Hyperlocal Urban Intelligence Ingestion Pipeline")
    print("=" * 60)
    
    print("\n[1/3] Triggering pipeline ingestion cycle...")
    summary = run_ingestion_pipeline()
    
    print(f"\n[2/3] Ingestion Summary:")
    print(f"  - Status:                   {summary['status']}")
    print(f"  - News Articles Fetched:    {summary['news_fetched']}")
    print(f"  - News Articles Inserted:   {summary['news_inserted']}")
    print(f"  - News Skipped (24h Dupes): {summary['news_skipped_duplicates']}")
    print(f"  - Weather Reports Fetched:  {summary['weather_fetched']}")
    print(f"  - Weather Reports Inserted: {summary['weather_inserted']}")
    
    if summary['errors']:
        print("\n  [Notice/Warnings from Pipeline]:")
        for err in summary['errors']:
            print(f"    * {err}")

    print("\n[3/3] SQLite Database Status:")
    total = count_reports()
    print(f"  - Total Persisted Reports:  {total}")
    
    reports = get_reports(limit=5)
    if reports:
        print("\n  Recent Reports in Database:")
        for r in reports:
            print(f"    * [{r['category']}] ({int(r['confidence']*100)}% {r['confidence_tier']}) {r['title'][:60]}... | Loc: {r.get('location')}")
    else:
        print("  - Database currently has 0 reports. (Configure NEWSDATA_API_KEY / OPENWEATHER_API_KEY in .env to ingest live external feeds).")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
