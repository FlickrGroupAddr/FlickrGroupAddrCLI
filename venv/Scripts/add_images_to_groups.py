import json
import argparse
import pprint
import flickrapi
import flickrapi.auth
import os.path
import datetime
import glob
import psycopg2
import uuid


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


def _persist_request_set_state( request_set_state, request_set_state_json_filename  ):
    with open( request_set_state_json_filename, "w" ) as request_set_state_handle:
        json.dump( request_set_state, request_set_state_handle, indent=4, sort_keys=True )


def _create_state_entry( request_set_state, photo_id, group_id ):
    state_key = _generate_state_key(photo_id, group_id)
    request_set_state[state_key] = {
        'photo_added': False,
        'fga_add_attempts': [],
    }

def _read_request_set_with_state( request_set_json_filename, request_set_state_json_filename ):

    with open( request_set_json_filename, "r") as request_set_handle:
        request_set_info = json.load( request_set_handle )['fga_request_set']

    if os.path.isfile( request_set_state_json_filename  ):
        with open(request_set_state_json_filename , "r") as request_set_state_handle:
            request_set_state_info = json.load(request_set_state_handle)
    else:
        # First time through, initialize state dictionary
        request_set_state_info = {}

    return {
        'request_set'           : request_set_info,
        'request_set_state'     : request_set_state_info,
    }


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
    arg_parser.add_argument( "postgres_creds_json", help="JSON file with DB credentials" )
    return arg_parser.parse_args()


def _generate_state_key( photo_id, group_id ):
    return f"photo_{photo_id}_group_{group_id}"


def _add_pic_to_group(flickrapi_handle, photo_id, group_id ):
    # Get current timestamp
    current_timestamp = datetime.datetime.now( datetime.timezone.utc ).replace( microsecond=0 )
    #print( f"Timestamp of this attempt: {current_timestamp.isoformat()}" )

    operation_status = {}

    try:
        print(f"\t* Attempting to add photo {photo_id} to group {group_id}")
        flickrapi_handle.groups.pools.add( photo_id=photo_id, group_id=group_id )

        # Success!
        print( "\t\tSuccess!")
        operation_status[ 'photo_added'] = True
        operation_status[ 'timestamp' ] =  current_timestamp.isoformat()
        operation_status[ 'status' ] = 'permstatus_success_added' 

    except flickrapi.exceptions.FlickrError as e:
        error_string = str(e)
        group_throttled_msg = "Error: 5:"
        adding_to_pending_queue_error_msg = "Error: 6:"
        if error_string.startswith(group_throttled_msg):
            operation_status = {
                'timestamp'         : current_timestamp.isoformat(),
                'status'            : 'defer_group_throttled_for_user',
                'error_message'     : error_string,
                'photo_added'       : False
            }
            print(f"\t\tGroup {group_id} has hit its throttle limit for the day")
        elif error_string.startswith(adding_to_pending_queue_error_msg):
            operation_status = {
                'timestamp'         : current_timestamp.isoformat(),
                'status'            : 'permstatus_success_added_queued',
                'photo_added'       : True
            }
            print( "\t\tSuccess (added to pending queue)!")
        else:
            print( f"\t\t{error_string}" )
            operation_status = {
                'timestamp'         : current_timestamp.isoformat(),
                'status'            : 'fail_' + str(e),
                'photo_added'       : False,
            }

    return operation_status


def _has_add_attempt_within_same_utc_day(state_entry):
    has_add_attempt_within_same_utc_day = False
    #seconds_in_one_day = 86400
    current_timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    for curr_add_attempt in state_entry['fga_add_attempts']:
        add_attempt_timestamp = datetime.datetime.fromisoformat(curr_add_attempt['timestamp'])
        if current_timestamp.date() == add_attempt_timestamp.date():
            has_add_attempt_within_same_utc_day = True
            break

    #print(f"\t\tDate {add_attempt_timestamp.date()} == {current_timestamp.date()}? {has_add_attempt_within_same_utc_day}")

    return has_add_attempt_within_same_utc_day


def _is_request_set_json( json_filename ):
    with open( json_filename, "r" ) as json_handle:
        parsed_json = json.load( json_handle )

    return 'fga_request_set' in parsed_json



def _get_group_memberships_for_pic( flickrapi_handle, pic_id ):
    pic_contexts = flickrapi_handle.photos.getAllContexts( photo_id=pic_id )

    #print( "Contexts:\n" + json.dumps(pic_contexts, indent=4, sort_keys=True))
    group_memberships = {}
    if 'pool' in pic_contexts:
        for curr_group in pic_contexts['pool']:
            group_memberships[ curr_group['id']] = curr_group

    #print( "Group memberships:\n" + json.dumps(group_memberships, indent=4, sort_keys=True))

    return group_memberships


def _get_group_memberships_for_user( flickrapi_handle ):
    return_groups = {}
    user_groups = flickrapi_handle.groups.pools.getGroups() 

    #print( "User memberships:\n" + json.dumps(user_groups, indent=4, sort_keys=True))
    if 'groups' in user_groups and 'group' in user_groups['groups']:
        for curr_group in user_groups['groups']['group']:
            #print("Processing group:\n" + json.dumps(curr_group, indent=4, sort_keys=True) )
            if 'id' in curr_group:
                return_groups[curr_group['id']] = None
             

    return return_groups

def _last_attempt_status_is_permanent_status( uuid_pk, db_cursor  ):
    sql_command = """
        SELECT final_status 
        FROM group_add_attempts
        WHERE submitted_request_fk = %s
        ORDER BY attempt_completed DESC
        LIMIT 1;
    """

    sql_params = ( uuid_pk, )
    db_cursor.execute( sql_command, sql_params )

    returned_row = db_cursor.fetchone()
    if returned_row is None:
        return False

    most_recent_status = returned_row[0]
    print( "Most recent status: {most_recent_status}" )
        
    return most_recent_status.startswith("permstatus_" )
    



def _add_pics_to_groups( args,  app_flickr_api_key_info, user_flickr_auth_info ):
    flickrapi_handle = _create_flickr_api_handle(app_flickr_api_key_info, user_flickr_auth_info)

    stats = {
        'skipped_already_added'     : 0,
        'skipped_too_soon'          : 0,
        'attempted_success'         : 0,
        'attempted_fail'            : 0,
    }

    with open( args.postgres_creds_json, "r" ) as pgsql_creds_handle:
        pgsql_creds = json.load( pgsql_creds_handle )

    user_submitted_requests = []

    # Pull all DB requests, ordered chronologically
    with psycopg2.connect(
        host        = pgsql_creds['db_host'],
        user        = pgsql_creds['db_user'],
        password    = pgsql_creds['db_passwd'],
        database    = pgsql_creds['db_dbname'] ) as db_conn:

        # Explaination of query
        #
        #   Inner query: get list of ID's with the date of the most recent time we attempted
        #                   to process this user request. The WHERE clause limits the rows to those
        #                   of interest (i.e., date most recent attempt is NULL (meaning we never tried it)
        #
        #
        #   Outer query: take the user submitted ID 

        with db_conn.cursor() as db_cursor:
            sql_command = """
                SELECT      inner_query.user_submitted_request_id,
	                        submitted_requests.flickr_user_cognito_id,
	                        submitted_requests.picture_flickr_id,
	                        submitted_requests.flickr_group_id
                FROM (
	                SELECT  submitted_requests.uuid_pk AS user_submitted_request_id,
                            DATE(MAX(attempt_started)) AS most_recent_attempt_date
                    FROM submitted_requests
                    LEFT JOIN group_add_attempts
                    ON submitted_requests.uuid_pk = group_add_attempts.submitted_request_fk
                    GROUP BY submitted_requests.uuid_pk
                ) AS inner_query
                JOIN submitted_requests
                ON inner_query.user_submitted_request_id = submitted_requests.uuid_pk
                WHERE inner_query.most_recent_attempt_date IS NULL 
                    OR (inner_query.most_recent_attempt_date <> date(now()))
                ORDER BY submitted_requests.request_datetime;
            """
            db_cursor.execute( sql_command )

            user_groups = {}
            groups_per_pic = {}

            for curr_user_request in db_cursor.fetchall():
                #print( "Got user request: " + json.dumps(curr_user_request, default=str) )

                user_request_details = {
                    "request_id"                    : curr_user_request[0],
                    "request_user_cognito_id"       : curr_user_request[1],
                    "request_flickr_picture_id"     : curr_user_request[2],
                    "request_flickr_group_id"       : curr_user_request[3],
                }

                print( "Got user request:\n" + json.dumps(user_request_details, indent=4, sort_keys=True, default=str) )

                add_attempt_guid    = str( uuid.uuid4() )
                request_id          = user_request_details[ 'request_id' ]

                # Let's see if previous add attempt status allows us to continue
                if _last_attempt_status_is_permanent_status( user_request_details['request_id'], db_cursor ) is True:
                    print( "Bailing due to previous status being permanent, no more attempts on this request permitted" )
                    continue

                sql_command = """
                    INSERT INTO group_add_attempts( uuid_pk, submitted_request_fk, attempt_started )
                    VALUES ( %s, %s, %s )
                    RETURNING uuid_pk;
                """

                sql_params = ( add_attempt_guid, request_id, "NOW()" )
                db_cursor.execute( sql_command, sql_params )

                add_attempt_guid = db_cursor.fetchone()[0]

                #print( f"GUID for this add attempt: {add_attempt_guid}" )


                # If this is the first time we've hit this user, pull their list of group memberships to see if if's even a
                # possibility to add it
                if user_request_details["request_user_cognito_id"] not in user_groups:
                    user_groups[ user_request_details["request_user_cognito_id"] ] = _get_group_memberships_for_user(
                        flickrapi_handle)
                    #print( "User memberships:\n" + 
                    #    json.dumps( user_groups[ user_request_details["request_user_cognito_id"] ], indent=4, sort_keys=True) )


                # If this is first time we've seen this picture, pull list of groups it's already in
                if user_request_details["request_flickr_picture_id"] not in groups_per_pic:
                    groups_per_pic[ user_request_details["request_flickr_picture_id"] ] = _get_group_memberships_for_pic(
                        flickrapi_handle, user_request_details["request_flickr_picture_id"] )

                    #print( "initialized cache of groups for pic " + user_request_details["request_flickr_picture_id"] + " to:" +
                    #    json.dumps( groups_per_pic[ user_request_details["request_flickr_picture_id"] ], indent=4,
                    #    sort_keys=True) )

                # If the user isn't in the requested group, mark a permfail
                if user_request_details['request_flickr_group_id'] not in \
                        user_groups[ user_request_details["request_user_cognito_id"] ]:

                    print( "User requested a picture be added into a group they are not in" )
                    attempt_status = "permstatus_fail_user_not_in_flickr_group"

                # If this pic is already in the requested group, skip it
                elif user_request_details['request_flickr_group_id'] in \
                    groups_per_pic[user_request_details["request_flickr_picture_id"]]:

                    print( f"Pic {user_request_details['request_flickr_picture_id']} already in group " +
                        f"{user_request_details['request_flickr_group_id']}" )

                    attempt_status = "permstatus_success_pic_already_in_group"

                else:
                    # Let's see if the most recent attempt status tells us not try to again (e.g., pic already in group)
                    print( "User is in requested group and the picture is not in the group, attempting group add API call" )

                    results_of_add_attempt = _add_pic_to_group( flickrapi_handle, 
                        user_request_details["request_flickr_picture_id"],
                        user_request_details['request_flickr_group_id'] )

                    attempt_status = results_of_add_attempt['status']

                        #print( "Results of add attempt:\n" + json.dumps(results_of_add_attempt) )

                # Do update of this attempt
                sql_command = """
                    UPDATE group_add_attempts 
                    SET attempt_completed = %s, final_status = %s
                    WHERE uuid_pk = %s;
                """

                sql_params = ( "NOW()", attempt_status, add_attempt_guid )
                db_cursor.execute( sql_command, sql_params )


            print( "Done printing requests" )

  
    return



    # Iterate over all JSON files in the specified directory
    for curr_json_file in glob.glob( os.path.join( args.request_set_json_dir, "*.json") ):
        if _is_request_set_json(curr_json_file):
            print(f"\nReading {curr_json_file}")
            request_set_state_json_filename = curr_json_file.replace(".json", ".state.json")
            #print( f"{curr_json_file} is a request set JSON")
            request_set_info = _read_request_set_with_state( curr_json_file, request_set_state_json_filename )
            #print( f"Got request set:\n{json.dumps(request_set_info, indent=4, sort_keys=True)}")

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
                            print( f"\tSkipping photo {current_pic_id} to group {current_group_id}, already added")
                            stats['skipped_already_added'] += 1
                            continue
                        elif _has_add_attempt_within_same_utc_day(state_entry):
                            print( f"\tSkipping photo {current_pic_id} to group {current_group_id}, already had a failure today (same UTC date)" )
                            stats['skipped_too_soon'] += 1
                            continue
                    else:
                        #print( f"INFO: Creating state entry for pic {current_pic_id} into group {current_group_id} as it wasn't in state info")
                        _create_state_entry(request_state_info, current_pic_id, current_group_id )
                        state_entry = request_state_info[state_key]

                    # Attempt add, because either state says we haven't succeeded yet or there *was* no state yet
                    #print( "attempting add")
                    _add_pic_to_group( flickrapi_handle, current_pic_id, current_group_id, state_entry )
                    if state_entry['fga_add_attempts'][-1]['status'] == 'success':
                        stats['attempted_success'] += 1
                    else:
                        stats['attempted_fail'] += 1

            _persist_request_set_state( request_set_info['request_set_state'], request_set_state_json_filename )
        else:
            #print( f"\tSkipping {curr_json_file}, not a request set file")
            pass

    return stats

def _main():
    args = _parse_args()

    # Get auth info
    app_flickr_api_key_info = _read_app_flickr_api_key_info( args )
    user_flickr_auth_info = _read_user_flickr_auth_info( args )

    # Ready to kick off the operations
    stats = _add_pics_to_groups( args, app_flickr_api_key_info, user_flickr_auth_info )
    print( "\nOperation stats:\n" + json.dumps(stats, indent=4, sort_keys=True))


if __name__ == "__main__":
    _main()
