import urllib.request
import urllib.error
import json
import sys

def get_url(url):
    try:
        response = urllib.request.urlopen(url)
        return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8')
            return {"error": str(e), "body": err_body}
        except:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

project_id = "b8e3cf9a"
print("Project Info:")
print(json.dumps(get_url(f"http://localhost:8000/project/{project_id}"), indent=2))
print("\nPipeline Status:")
print(json.dumps(get_url(f"http://localhost:8000/project/{project_id}/pipeline-status"), indent=2))
print("\nDebug Jobs:")
print(json.dumps(get_url(f"http://localhost:8000/debug-jobs"), indent=2))
