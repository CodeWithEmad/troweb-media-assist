import requests
import os


url = "https://lernito-ai-tutor.troweb.app/api/v1/graphql"
video_extensions = (".mp4", ".mov", ".mkv", ".avi")


def send_gql_request(query, variables):
    # Send the mutation request with variables
    response = requests.post(
        url,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {os.getenv('TW_TOKEN')}"},
    )
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()

        # Check if there are any errors in the GraphQL response
        if "errors" in data:
            errors = data["errors"]
            print("GraphQL Errors:")
            for error in errors:
                print(error["message"])
        else:
            return data

    else:
        print("Request failed with status code:", response.status_code)
        print(response.text)
        # raise response


def create_batch_job():
    mutation = """
    mutation {
      createBulkOperation {
        _id
      }
    }
  """
    return send_gql_request(mutation, {})["data"]["createBulkOperation"]["_id"]


def start_batch_job(job_id):
    print(f"starting the job {job_id}")
    mutation = """
    mutation startJob($jobId: ObjectId!){
      startBulkOperation(_id: $jobId) {
        status
      }
    }
  """
    return send_gql_request(mutation, {"jobId": job_id})


def add_bulk_batch(actions, job_id):
    print(f"Adding batch of {len(actions)} actions to job {job_id}")
    mutation = """
    mutation addBulkActions($jobId: ObjectId! , $actions: [BulkActionInput!]! ) {
      addBulkActions(bulkOperationId: $jobId, actions: $actions) {
        _id
        status
        totalActions
        processedActions
        errors
      }
    }
  """
    variables = {"jobId": job_id, "actions": actions}
    return send_gql_request(mutation, variables)


def get_action(video, parent_id):
    return {
        "createVideo": {
            "tw_title": video.get("title", "-")[:170],
            "transcript": video.get("transcription", "-"),
            "publicUrl": video.get("url", "-"),
            "tw_parentId": parent_id,
        }
    }


def insert_all(videos, parent_id):
    actions = []
    job_id = create_batch_job()
    print(f"Created Job {job_id}")
    for q in videos:
        try:
            actions.append(get_action(q, parent_id))
        except Exception as e:
            print(f"Failed to add item {q} - Error {e}")
        if len(actions) > 50:
            add_bulk_batch(actions, job_id)
            actions = []
    add_bulk_batch(actions, job_id)
    start_batch_job(job_id)
