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


def _create_state_entry( request_set_state, photo_id, group_id ):
    state_key = _generate_state_key(photo_id, group_id)
    request_set_state[state_key] = {
        'photo_added': False,
        'fga_add_attempts': [],
    }

def _read_request_set_with_state( args ):
    args.request_set_json, args.request_set_state_json

    with open( args.request_set_json, "r") as request_set_handle:
        request_set_info = json.load( request_set_handle )['fga_request_set']

    if os.path.isfile( args.request_set_state_json ):
        with open(args.request_set_state_json, "r") as request_set_state_handle:
            request_set_state_info = json.load(request_set_state_handle)
    else:
        # First time through, initialize state dictionary
        request_set_state_info = {}

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


def _generate_state_key( photo_id, group_id ):
    return f"photo_{photo_id}_group_{group_id}"


def _add_pic_to_group(flickrapi_handle, photo_id, group_id, state_entry ):
    # Get current timestamp
    current_timestamp = datetime.datetime.now( datetime.timezone.utc ).replace( microsecond=0 )
    #print( f"Timestamp of this attempt: {current_timestamp.isoformat()}" )

    try:
        print(f"Attempting to add photo {photo_id} group {group_id}")
        flickrapi_handle.groups.pools.add( photo_id=photo_id, group_id=group_id )

        # Success!
        print( "\tSuccess!")
        state_entry['photo_added'] = True
        state_entry_add_attempt_details = {
            'timestamp' : current_timestamp.isoformat(),
            'status'    : 'success',
        }

    except flickrapi.exceptions.FlickrError as e:
        print( f"\t{str(e)}" )
        state_entry_add_attempt_details = {
            'timestamp'     : current_timestamp.isoformat(),
            'status'        : 'fail',
            'error_message' : str(e),
        }

    state_entry['fga_add_attempts'].append( state_entry_add_attempt_details )


def _has_add_attempt_within_one_day(state_entry):
    has_add_attempt_within_one_day_prior = False
    seconds_in_one_day = 86400
    for curr_add_attempt in state_entry['fga_add_attempts']:
        add_attempt_timestamp = datetime.datetime.fromisoformat(curr_add_attempt['timestamp'])
        current_timestamp = datetime.datetime.now( datetime.timezone.utc ).replace( microsecond=0 )
        if (current_timestamp - add_attempt_timestamp).total_seconds() <= seconds_in_one_day:
            has_add_attempt_within_one_day_prior = True
            break

    return has_add_attempt_within_one_day_prior


def _add_pics_to_groups( args,  app_flickr_api_key_info, user_flickr_auth_info ):
    # Read group membership info
    #user_group_membership_info = _read_user_groups( args )

    request_set_info = _read_request_set_with_state( args )
    #print( f"Got request set:\n{json.dumps(request_set_info, indent=4, sort_keys=True)}")

    flickrapi_handle = _create_flickr_api_handle( app_flickr_api_key_info, user_flickr_auth_info )

    request_state_info = request_set_info['request_set_state']

    for current_pic_id in request_set_info['request_set']:
        current_pic_info = request_set_info['request_set'][current_pic_id]
        #print( f"Current entry:\n{json.dumps(request_set_info['request_set'][current_pic_id], indent=4, sort_keys=True)}")

        # Iterate over all the groups we're thinking to add this pic to
        for current_group_entry in current_pic_info:
            # Take first token (separated by whitespace) as the group NSID. The rest is human readability fluff
            current_group_id = current_group_entry.split()[0]
            # Check state on this entry to make sure it wasn't already added
            state_key = _generate_state_key( current_pic_id, current_group_id )
            #print( f"State key: {state_key}")
            if state_key in request_state_info:
                state_entry = request_state_info[state_key]
                if state_entry['photo_added']:
                    print( f"Skipping photo {current_pic_id} to group {current_group_id}, already added")
                    continue
                elif _has_add_attempt_within_one_day(state_entry):
                    print( f"Skipping photo {current_pic_id} to group {current_group_id}, already had a failure within the last day" )
                    continue
            else:
                #print( f"INFO: Creating state entry for pic {current_pic_id} into group {current_group_id} as it wasn't in state info")
                _create_state_entry(request_state_info, current_pic_id, current_group_id )
                state_entry = request_state_info[state_key]

            # Attempt add, because either state says we haven't succeeded yet or there *was* no state yet
            #print( "attempting add")
            _add_pic_to_group( flickrapi_handle, current_pic_id, current_group_id, state_entry )

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