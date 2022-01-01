import json
import argparse
import pprint
import flickrapi
import flickrapi.auth
import os.path
import datetime


def _create_flickr_api_handle( app_flickr_api_key_info, user_flickr_auth_info ):
    # Create an OAuth User Token that flickr API library understands
    api_access_level = "write"
    flickrapi_user_token = flickrapi.auth.FlickrAccessToken(
        user_flickr_auth_info['user_oauth_token'],
        user_flickr_auth_info['user_oauth_token_secret'],
        api_access_level,
        user_flickr_auth_info['user_fullname'],
        user_flickr_auth_info['username'],
        user_flickr_auth_info['user_nsid'])

    flickrapi_handle = flickrapi.FlickrAPI(app_flickr_api_key_info['api_key'],
                                           app_flickr_api_key_info['api_key_secret'],
                                           token=flickrapi_user_token,
                                           store_token=False,
                                           format='parsed-json')

    return flickrapi_handle


def _persist_request_set_state( args, request_set_state ):
    with open( args.request_set_state_json, "w" ) as request_set_state_handle:
        json.dump( request_set_state, request_set_state_handle, indent=4, sort_keys=True )


def _read_request_set_with_state( args ):
    args.request_set_json, args.request_set_state_json

    with open( args.request_set_json, "r") as request_set_handle:
        request_set_info = json.load( request_set_handle )['group_add_requests']

    if os.path.isfile( args.request_set_state_json ):
        with open(args.request_set_state_json, "r") as request_set_state_handle:
            request_set_state_info = json.load(request_set_state_handle)
    else:
        # First time through, create the state
        request_set_state_info = []
        for curr_add_request in request_set_info:
            # initialize as same object
            curr_state_info = {}
            curr_state_info.update( curr_add_request )

            # Add array of add attempts so we can note things like attepmt timestamp, result, and next attempt timestamp
            curr_state_info[ 'fga_add_attempts' ] = []

            request_set_state_info.append( curr_state_info )


    return {
        'request_set'           : request_set_info,
        'request_set_state'     : request_set_state_info,
    }


def _read_user_groups( args ):
    with open( args.group_membership_json, "r") as user_group_membership_handle:
        user_group_info = json.load( user_group_membership_handle )

    return user_group_info


def _read_user_flickr_auth_info(args):
    with open( args.user_auth_info_json, "r") as user_auth_info_handle:
        user_auth_info = json.load( user_auth_info_handle )

    return user_auth_info


def _read_app_flickr_api_key_info(args):
    with open(args.app_api_key_info_json, "r") as app_api_key_info_handle:
        app_api_key_info = json.load(app_api_key_info_handle)

    return app_api_key_info


def _parse_args():
    arg_parser = argparse.ArgumentParser(description="Get list of groups for this user")
    arg_parser.add_argument( "app_api_key_info_json", help="JSON file with app API auth info")
    arg_parser.add_argument( "user_auth_info_json", help="JSON file with user auth info")
    arg_parser.add_argument( "group_membership_json", help="JSON with user's group membership info")
    arg_parser.add_argument( "request_set_json", help="JSON file with picture->group add requests")
    arg_parser.add_argument( "request_set_state_json", help="JSON file with state for all requests in the request group")
    return arg_parser.parse_args()


def _add_pics_to_groups( args,  app_flickr_api_key_info, user_flickr_auth_info ):
    # Read group membership info
    user_group_membership_info = _read_user_groups( args )

    request_set_info = _read_request_set_with_state( args )
    #print( f"Got request set:\n{json.dumps(request_set_info, indent=4, sort_keys=True)}")

    flickrapi_handle = _create_flickr_api_handle( app_flickr_api_key_info, user_flickr_auth_info )

    for current_request_set_entry in request_set_info['request_set']:
        print( f"Current entry:\n{json.dumps(current_request_set_entry, indent=4, sort_keys=True)}")

        # Make sure the requested image belongs to this user

        # Make sure the user is a member of the group indicated

        # Get current timestamp
        current_timestamp = datetime.datetime.now( datetime.timezone.utc ).replace( microsecond=0 )
        #print( f"Timestamp of this attempt: {current_timestamp.isoformat()}" )

        response_code = flickrapi_handle.groups.pools.add(
            photo_id=current_request_set_entry['picture_id'],
            group_id=current_request_set_entry['group_nsid'] )

        if response_code is None:
            # Success!
            print( f"Photo {current_request_set_entry['picture_id']} added to group ID {current_request_set_entry['group_nsid']} successfully!" )
        else:
            print( f"Error {response_code} hit when adding Photo {current_request_set_entry['picture_id']} added to group ID {current_request_set_entry['group_nsid']}" )


        break


    # # Test our handle, print out our authenticated NSID or something
    # user_groups = flickrapi_handle.groups.pools.getGroups()['groups']['group']
    #
    # #pprint.pprint( user_groups )
    # culled_group_membership_info = {}
    # for curr_user_group in user_groups:
    #     culled_group_membership_info[ curr_user_group['name'] ] = {
    #         'nsid': curr_user_group['nsid']
    #     }
    #
    # with open( args.group_membership_json, "w") as group_membership_handle:
    #     json.dump( culled_group_membership_info, group_membership_handle, indent=4, sort_keys=True )

    _persist_request_set_state( args, request_set_info['request_set_state'] )



def _main():
    args = _parse_args()

    # Get auth info
    app_flickr_api_key_info = _read_app_flickr_api_key_info( args )
    user_flickr_auth_info = _read_user_flickr_auth_info( args )

    # Ready to kick off the operations
    _add_pics_to_groups( args, app_flickr_api_key_info, user_flickr_auth_info )


if __name__ == "__main__":
    _main()