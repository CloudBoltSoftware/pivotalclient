import requests
import logging
import inspect
import sys
from copy import deepcopy

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

        Args:
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
        
        Args:
            endpoint: a URL to POST
            json: the jsonifiable (e.g. dict or list) data to send to Pivotal
        """
        headers = self.auth_headers
        resp = requests.post(endpoint, json=json, headers=headers)
        if not resp or not 200 <= resp.status_code < 300:
            raise ApiError('POST {} {}'.format(endpoint, resp.status_code))
        return resp.json()

    def _put(self, endpoint, json):
        """Issue a PUT to Pivotal Tracker.

        Args:
            endpoint: a URL to PUT
            json: the jsonifiable (e.g. dict or list) data to send to Pivotal
        """
        headers = self.auth_headers
        resp = requests.put(endpoint, json=json, headers=headers)
        if not resp or not 200 <= resp.status_code < 300:
            raise ApiError('PUT {} {}'.format(endpoint, resp.status_code))
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

    def get_story(self, story_id):
        self._verify_project_id_exists()
        return self._get(self.api_story.format(story_id))

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

    def update_story(self, story_id, fields):
        self._verify_project_id_exists()
        uri = self.api_story.format(story_id)
        results = self._put(uri, fields)
        return results

    @staticmethod
    def _desc_for_external_story(context, template):
        tmpl = '[External Story #{external_story[external_id]}]'
        tmpl += '({integration[base_url]}/tickets/{external_story[external_id]})'
        tmpl += 'filed by {external_story[external_requester]}.'
        if template:
            tmpl = template
        return tmpl.format(**context)

    @staticmethod
    def _name_for_external_story(context, template):
        tmpl = 'External Story: {external_story[name]}'
        if template:
            tmpl = template
        return tmpl.format(**context)

    def create_stories_from_integration_stories(self, desc_template=None, name_template=None):
        """ For each external integration story (e.g. a ZenDesk ticket), create a story.
        
        Notes On Template Context:
            We use string.format() on a **dict of dicts, so your templates may use dictionary-style accessors in the
            fields, such as "Ticket ID: {external_story[external_id]} 
        
        Args:
            desc_template: a .format() template used to populate story description. Context available described below.
            name_template: a .format() template used to populate story name. Context available described below.
        
        Context Available:
            external_story: see https://www.pivotaltracker.com/help/api/rest/v5#external_story_resource
            integration: see https://www.pivotaltracker.com/help/api/rest/v5#integration_resource
                (note: this may actually be an instance of a zendesk_integration, bugzilla_integration, etc.)
            nl: '\n', a linebreak.
        """
        self._verify_project_id_exists()
        external_stories = self.get_all_integration_stories()
        integrations = {i.get('id'): i for i in self.get_integrations()}
        results = []
        for es in external_stories:
            wrapped_es = deepcopy(es)

            context = {
                'external_story': es,
                'integration': integrations[es['integration_id']],
                'nl': '\n',
            }

            story_name = PivotalClient._name_for_external_story(context, name_template)
            wrapped_es['name'] = story_name

            story_desc = PivotalClient._desc_for_external_story(context, desc_template)
            wrapped_es['description'] = story_desc

            # Remove fields we don't need/want.
            wrapped_es.pop('state', None)
            wrapped_es.pop('external_requester', None)
            if 'requested_by_id' not in wrapped_es:
                print("Missing requested_by_id on {} [{}]".format(story_name, es.get('external_id')))
            wrapped_es.pop('requested_by_id', None)

            results.append((es, self.create_story(wrapped_es)))
        return results
