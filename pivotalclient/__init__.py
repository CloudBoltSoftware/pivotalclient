import requests
import logging
import inspect
import sys

DEBUG = False

# Debugging mode for this script means that you'll get some extra print
# statements, as well as full requests library debugging output.
if DEBUG:
    # Enable httplib debugging
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # Initialize requests logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


class ApiError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class AttrDict(dict):
    """Magic dictionary subclass that treats keys as instance attributes.

    Usage:
        ad = AttrDict({'hello': 'world'})
        assertEquals(ad.hello, 'world')
    """
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class PivotalClient:
    def __init__(self, api_token, account_id=None, project_id=None, api_root=None):
        self.auth_headers = {'X-TrackerToken': api_token}
        self.account_id = account_id
        self.project_id = project_id

        if not api_root:
            api_root = 'https://www.pivotaltracker.com/services/v5'
        self.api_root = api_root

        self.api_accounts = '{}/accounts'.format(self.api_root)
        if self.account_id:
            self.api_account = '{}/{}'.format(self.api_accounts, self.account_id)
            self.api_account_memberships = '{}/memberships'.format(self.api_account)

        self.api_projects = '{}/projects'.format(self.api_root)
        if self.project_id:
            self.api_project = '{}/{}'.format(self.api_projects, self.project_id)
            self.api_project_memberships = '{}/memberships'.format(self.api_project)
            self.api_stories = '{}/stories'.format(self.api_project, self.project_id)
            self.api_story = '{}/stories/{}'.format(self.api_project, '{}')
            self.api_activity = '{}/stories/{}/activity'.format(self.api_project, '{}')
            self.api_integrations = '{}/integrations'.format(self.api_project)
            self.api_integration = '{}/{}'.format(self.api_integrations, '{}')
            self.api_integration_stories = '{}/{}/stories'.format(self.api_integrations, '{}')

        self.api_filter = {'date_format': 'millis', 'filter': None}

    def _get(self, endpoint, querystring=None, with_envelope=False):
        """Issue a GET to Pivotal Tracker.

        endpoint: a URL to GET
        querystring: a dict of querystring parameters
        """
        _querystring = querystring.copy() if querystring else {}
        if with_envelope:
            _querystring['envelope'] = 'true'
        if DEBUG:
            print("DEBUG: querystring={}".format(querystring))
        headers = self.auth_headers

        resp = requests.get(endpoint, params=_querystring, headers=headers)
        if not resp or not 200 <= resp.status_code < 300:
            raise ApiError('GET {} {}'.format(endpoint, resp.status_code))
        return resp.json()

    def _post(self, endpoint, json):
        """Issue a POST to Pivotal Tracker.
        
        endpoint: a URL to POST
        json: the jsonifiable (e.g. dict or list) data to send to Pivotal
        """
        headers = self.auth_headers
        resp = requests.post(endpoint, json=json, headers=headers)
        if not resp or not 200 <= resp.status_code < 300:
            raise ApiError('GET {} {}'.format(endpoint, resp.status_code))
        return resp.json()
    
    def _get_all(self, endpoint, querystring=None):
        DEFAULT_PAGE_LIMIT = 1000
        _querystring = querystring.copy() if querystring else {}
        _querystring['limit'] = DEFAULT_PAGE_LIMIT
        _querystring['offset'] = 0
        results = []
        while True:
            response = self._get(endpoint, _querystring, with_envelope=True)
            
            # No results in this page? We're done!
            if len(response.get('data', [])) == 0:
                break

            # Extend our results with the results provided.
            results.extend(response.get('data'))
            
            # Update the page limit from the server-specified limit.
            _querystring['limit'] = response.get('pagination', {}).get('limit', DEFAULT_PAGE_LIMIT)
            
            # Increment the offset by the server-specified limit to get the next page.
            _querystring['offset'] += _querystring['limit']
        return results
    
    def _verify_project_id_exists(self):
        if not self.project_id:
            caller_name = 'UNKNOWN'
            try:
                caller_name = sys.getframe(1).f_code.co_name
            except Exception as ex:
                caller_name = inspect.stack()[1][3]
            raise ApiError('Project ID not set on API connection and is required by {}().'.format(caller_name))

    def _verify_account_id_exists(self):
        if not self.account_id:
            caller_name = 'UNKNOWN'
            try:
                caller_name = sys.getframe(1).f_code.co_name
            except Exception as ex:
                caller_name = inspect.stack()[1][3]
            raise ApiError('Account ID not set on API connection and is required by {}().'.format(caller_name))

    def get_stories_by_filter(self, pivotal_filter):
        self._verify_project_id_exists()
        filt = self.api_filter.copy()
        filt['filter'] = pivotal_filter
        uri = self.api_stories
        results = self._get_all(uri, querystring=filt)
        return results
    
    def get_stories_by_label(self, label):
        self._verify_project_id_exists()
        filt = {'filter': 'label:"{}"'.format(label)}
        uri = self.api_stories
        results = self._get_all(uri, querystring=filt)
        return results
    
    def get_story_activities(self, story_id):
        self._verify_project_id_exists()
        uri = self.api_activity.format(story_id)
        results = self._get(uri)
        return results
    
    def get_project_memberships(self):
        self._verify_project_id_exists()
        uri = self.api_project_memberships
        results = self._get(uri)
        return results
    
    def get_account_memberships(self):
        self._verify_account_id_exists()
        uri = self.api_account_memberships
        results = self._get(uri)
        return results
    
    def get_integrations(self):
        self._verify_project_id_exists()
        uri = self.api_integrations
        results = self._get(uri)
        return results
    
    def get_integration(self, integration_id):
        self._verify_project_id_exists()
        uri = self.api_integration.format(integration_id)
        results = self._get(uri)
        return results
    
    def get_integration_stories(self, integration_id):
        self._verify_project_id_exists()
        querystring = {'exclude_linked': 'true'}
        uri = self.api_integration_stories.format(integration_id)
        results = self._get(uri, querystring=querystring)
        return results
    
    def get_all_integration_stories(self):
        results = []

        integrations = self.get_integrations()
        for integration in integrations:
            integration_stories = self.get_integration_stories(integration.get('id'))
            results.extend(integration_stories)

        return results

    def create_story(self, story_dict):
        self._verify_project_id_exists()
        uri = self.api_stories
        results = self._post(uri, story_dict)
        return results

    def create_stories_from_integration_stories(self, template=None):

        def _desc_for_zendesk_ticket(base_url, ticket_id, requester, template):
            tmpl = '[ZenDesk Ticket #{ticket_id}]({base_url}/tickets/{ticket_id}) filed by {requester}.'
            if template:
                tmpl = template
            return tmpl.format(
                ticket_id=ticket_id,
                base_url=base_url,
                requester=requester
            )

        self._verify_project_id_exists()
        external_stories = self.get_all_integration_stories()
        integrations = {i.get('id'): i for i in self.get_integrations()}
        results = []
        for es in external_stories:
            es.pop('state')
            es_requester = es.pop('external_requester')
            int_base_url = integrations[es['integration_id']]['base_url']
            if integrations[es['integration_id']]['kind'] == 'zendesk_integration':
                es['description'] = _desc_for_zendesk_ticket(int_base_url, es['external_id'], es_requester, template)
                es['name'] = 'ZD Ticket: {}'.format(es['name'])
            results.append(self.create_story(es))
        return results
