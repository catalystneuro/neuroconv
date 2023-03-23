import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..utils.path_expansion import AbstractPathExpander

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly", "https://www.googleapis.com/auth/drive.readonly"]


class GoogleDrivePathExpander(AbstractPathExpander):
    """

    Example
    -------
    >>> from neuroconv.tools.google_drive import GoogleDrivePathExpander
    >>> path_expander = GoogleDrivePathExpander("/path/to/credentials.json")
    >>> list(path_expander.list_directory("1XssGXlQhDco4n8QPYzKX7pkQQKFcRUug"))
    >>> path_expander.expand_paths(
    ...     dict(
    ...         spikeglx=dict(
    ...             folder="1XssGXlQhDco4n8QPYzKX7pkQQKFcRUug",
    ...             paths=dict(file_path="sub-{subject_id}/sub-{subject_id}_ses-{session_id}")
    ...         )
    ...     )
    ... )

    """

    def __init__(self, credentials_file_path: str):
        """
        Initialize a new GoogleDrive.

        Parameters
        ----------
        credentials_file_path : str
            Path to credentials.json
        """

        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        try:
            self.service = build("drive", "v3", credentials=creds)
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print(f"An error occurred: {error}")

    def list_directory(self, folder):
        """

        Parameters
        ----------
        folder: str
            String of seemingly random characters in URL of Google Drive folder.

        Yields
        ------
        str

        """

        def _list_dir(item_id: str = None, current_path: str = ""):
            query = f"'{item_id}' in parents"
            results = self.service.files().list(q=query, fields="nextPageToken, files(id, name, mimeType)").execute()
            items = results.get("files", [])

            for item in items:
                # If the item is a folder, recursively traverse its contents
                new_path = f"{current_path}/{item['name']}"
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    yield from _list_dir(item["id"], new_path)
                else:
                    yield new_path[1:]

        yield from _list_dir(folder)
