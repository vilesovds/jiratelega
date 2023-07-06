from jira import JIRA
from configmanager import config
import logging

# By default, the client will connect to a Jira instance started from the Atlassian Plugin SDK
# (see https://developer.atlassian.com/display/DOCS/Installing+the+Atlassian+Plugin+SDK for details).
jira = JIRA(
    server=config['jira']['server'],
    basic_auth=(
        config['jira']['auth']['email'],
        config['jira']['auth']['token']
    )
)
logger = logging.getLogger(__name__)


def create_task(description, request_type, assignee='', files=None, reporter=None):
    if not files:
        files = []
    project_key = config['jira']['project_key']

    sds = jira.service_desks()
    for sd in sds:
        if sd.projectKey == project_key:
            sd_id = sd.id
            break
    else:
        logger.error(f'Service desk not found for project key {project_key}')
        return None

    req_type_id = jira.request_type_by_name(sd_id, request_type)

    data = dict()
    data["serviceDeskId"] = sd_id
    data['requestTypeId'] = int(req_type_id.id)
    data['requestFieldValues'] = {
        'summary': 'New issue from telegram'
    }
    try:
        issue = jira.create_customer_request(data)
        issue.update(description=description)
    except Exception as error:
        logger.error(error)
        return None

    if reporter:
        users = jira.search_users(query=reporter)
        user = users[0] if users else None
        if user:
            logger.info(f'found account id: {user.accountId} for reporter')
            issue.update(reporter={'accountId': user.accountId})
        else:
            logger.info(f"could not found account id for reporter user {reporter}")

    if assignee != '':
        try:
            jira.assign_issue(issue, assignee)
        except Exception as error:
            logger.error(error)

    for file in files:
        try:
            jira.add_attachment(issue, file['data'], file['filename'])
        except Exception as error:
            logger.error(error)

    return issue.permalink()


if __name__ == '__main__':
    pass
