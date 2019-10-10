import os

from flask import Flask, Response, request

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import xml.dom.minidom as minidom
import time

import redis

if "DEBUG_MODE" in os.environ:
    debug_mode = True
else:
    debug_mode = False

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ["FLASK_SECRET"]
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

r = redis.Redis(host=os.environ["REDIS_HOST"], port=os.environ["REDIS_PORT"], db=os.environ["REDIS_DB"])


# Debug message
def debug_message(message):
    if debug_mode:
        print(message if message is not None else 'message is None')


# The main entrypoint
@app.route('/DSess/services/DSess', methods=['POST'])
def dsess_runtime():
    root = ET.fromstring(request.data)
    body = root[0]
    action = body[0]
    debug_message(request.headers)
    soap_action = str(request.headers['Soapaction']).lower().replace('"', '', 2)
    debug_message("soapaction: " + soap_action)

    response_body = None
    if 'joinReplicaSet'.lower() in soap_action:
        debug_message('join')
        response_body = join_replica_set(action)
    elif 'ping'.lower() in soap_action:
        debug_message('ping')
        response_body = ping(action)
    elif 'getUpdates'.lower() in soap_action:
        debug_message('getUpdates')
        response_body = get_updates(action)
    elif 'replicaShutdown'.lower() in soap_action:
        debug_message('replicaShutdown')
        response_body = replica_shutdown(action)
    elif 'getRealmName'.lower() in soap_action:
        debug_message('getRealmName')
        response_body = get_realm_name(action)
    elif 'createSession'.lower() in soap_action:
        debug_message('createSession')
        debug_message(tostring(root))
        response_body = create_session(action)
    elif 'getSession'.lower() in soap_action:
        debug_message('getSession')
        debug_message(tostring(root))
        response_body = get_session(action)
    elif 'idleTimeout'.lower() in soap_action:
        debug_message('idleTimeout')
        debug_message(tostring(root))
        response_body = idle_timeout(action)
    elif 'terminateSession'.lower() in soap_action:
        debug_message('terminateSession')
        debug_message(tostring(root))
        response_body = terminate_session(action)
    elif 'changeSession'.lower() in soap_action:
        debug_message('changeSession')
        debug_message(tostring(root))
        response_body = change_session(action)
        debug_message(tostring(response_body))
    else:
        debug_message("Unknown operation: " + soap_action)
        # debug_message(action.tag)

    resp = Response()
    resp.data = minidom.parseString(
        tostring(response_body)
    ).toprettyxml(encoding='UTF-8').decode().replace('\t', '').strip()
    resp.headers.set('connection', 'close')
    resp.headers.set('server', 'Apache Axis C++/1.6.a')
    resp.headers.set('content-type', 'text/xml')

    return resp

    # return Response(response_body, mimetype='text/xml')


# Unfortunately, the ISAM LMI always uses localhost:2035/DSess/services/DSessAdmin and thus this is useless
@app.route('/DSess/services/DSessAdmin', methods=['POST'])
def dsess_admin():
    root = ET.fromstring(request.data)
    body = root[0]
    action = body[0]

    debug_message(action.tag)


def join_replica_set(body):
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    instance = body.find('{http://sms.am.tivoli.com}instance').text
    debug_message('instance: ' + instance)
    capabilities = body.find('{http://sms.am.tivoli.com}capabilities').text
    debug_message('capabilities: ' + capabilities)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)

    # Verify if the replica is in the set
    ris = replica_in_set(replica, replica_set)
    if ris is True:
        debug_message('already joined')
    else:
        debug_message('joining replica-set')
        # Join it
        replica_join_replica_set(replica_set, replica)

    # A bunch of static elements
    join_replica_set_response = Element('ns1:joinReplicaSetResponse')
    join_replica_set_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    join_replica_set_return = Element('ns1:joinReplicaSetReturn')
    result = Element('ns1:result')
    result.text = '952467756'
    join_replica_set_return.append(result)

    current_key = Element('ns1:currentKey')
    current_key.text = 'iuhew9873hkediuyer987'
    join_replica_set_return.append(current_key)

    old_key = Element('ns1:oldKey')
    old_key.text = 'iuhew9873hkediuyer987'
    join_replica_set_return.append(old_key)

    current_key_id = Element('ns1:currentKeyID')
    current_key_id.text = '0'
    join_replica_set_return.append(current_key_id)

    old_key_id = Element('ns1:oldKeyID')
    old_key_id.text = '0'
    join_replica_set_return.append(old_key_id)

    current_key_age = Element('ns1:currentKeyAge')
    current_key_age.text = '-1'
    join_replica_set_return.append(current_key_age)

    join_replica_set_response.append(join_replica_set_return)
    return envelope_soap_body(join_replica_set_response)


# Easily verify whether a value is in a Redis list
def string_in_list(list_key, string_value):
    rllen = r.llen(list_key)
    if rllen == 0:
        return False
    for i in range(0, r.llen(list_key)):
        v = r.lindex(list_key, i)
        if v.decode('utf-8') == string_value:
            return True

    return False


# Verify whether replica is in a given set
def replica_in_set(replica_name, replica_set_name):
    redis_replicaset_replicas = replica_set_name + ':replicas'
    return string_in_list(redis_replicaset_replicas, replica_name)


# Join a replica set
def replica_join_replica_set(replica_set, replica_name):
    redis_replicaset_replicas = replica_set + ':replicas'
    r.lpush(redis_replicaset_replicas, replica_name)
    r.set(replica_name + ':set', replica_set)


# Leave replica set
def leave_replica_set(replica_name):
    redis_replica_set = r.get(replica_name + ':set')
    # debug_message('replica "' + replica_name + '" is in: ' + replica_set)
    if redis_replica_set is not None:
        replica_set = redis_replica_set.decode('utf-8')
        ris = replica_in_set(replica_name, replica_set)
        if ris is not None and ris:
            r.lrem(replica_set + ':replicas', -1, replica_name)
            r.delete(replica_name + ':set')


# Probably WebSEAL health-checking the DSC.
def ping(body):
    ping_response = Element('ns1:pingResponse')
    ping_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    ping_return = Element('ns1:pingReturn')
    ping_return.text = '952467756'

    ping_response.append(ping_return)

    return envelope_soap_body(ping_response)


# Honestly, no idea what this is, it's super static random keys and if you reply immediately,
# WebSEAL will punish you. :)
def get_updates(body):
    response_by = int(body.find('{http://sms.am.tivoli.com}responseBy').text)

    get_updates_response = Element('ns1:getUpdatesResponse')
    get_updates_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    get_updates_return = Element('ns1:getUpdatesReturn')

    result = Element('ns1:result')
    result.text = '952467756'
    get_updates_return.append(result)

    new_key = Element('ns1:newKey')
    new_key.text = 'iuhew9873hkediuyer987'
    get_updates_return.append(new_key)

    new_key_id = Element('ns1:newKeyID')
    new_key_id.text = '0'
    get_updates_return.append(new_key_id)

    get_updates_response.append(get_updates_return)
    time.sleep(response_by)
    return envelope_soap_body(get_updates_response)


# Removes the replica from the replica_set, you might want this for administration later on
def replica_shutdown(body):
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    leave_replica_set(replica)

    replica_shutdown_response = Element('ns1:replicaShutdownResponse')
    replica_shutdown_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    replica_shutdown_return = Element('ns1:replicaShutdownReturn')
    replica_shutdown_return.text = '952467756'
    replica_shutdown_response.append(replica_shutdown_return)

    return envelope_soap_body(replica_shutdown_response)


# Don't know what this is, it just replies with realm='ISAM-Distributed-Session-Cache'
def get_realm_name(body):
    get_realm_name_response = Element('ns1:getRealmNameResponse')
    get_realm_name_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    get_realm_name_return = Element('ns1:getRealmNameReturn')

    result = Element('ns1:result')
    result.text = '952467756'
    get_realm_name_return.append(result)

    realm = Element('ns1:realm')
    realm.text = 'ISAM-Distributed-Session-Cache'
    get_realm_name_return.append(realm)

    get_realm_name_response.append(get_realm_name_return)
    return envelope_soap_body(get_realm_name_response)


def create_session(body):
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)
    session_id = body.find('{http://sms.am.tivoli.com}sessionID').text
    debug_message('sessionID: ' + session_id)
    session_limit = body.find('{http://sms.am.tivoli.com}sessionLimit').text
    debug_message('sessionLimit: ' + session_limit)

    # Loop over every 'data' credential attribute, and store it in Redis
    for data in body.findall('{http://sms.am.tivoli.com}data'):
        data_class = data.find('{http://sms.am.tivoli.com}dataClass').text
        # Store in Redis, this is based on session_id and 'data_class'
        redis_session_add_or_modify_attribute(session_id, data_class, data)

    # Persist the session in Redis here
    redis_create_session(replica_set, session_id)

    # The rest is static values
    create_session_response = Element('ns1:createSessionResponse')
    create_session_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    create_session_return = Element('ns1:createSessionReturn')

    result = Element('ns1:result')
    result.text = '952467756'
    create_session_return.append(result)

    version = Element('ns1:version')
    version.text = '0'
    create_session_return.append(version)

    stack_depth = Element('ns1:stackDepth')
    stack_depth.text = '1'
    create_session_return.append(stack_depth)

    clear_on_read_data_present = Element('ns1:clearOnReadDataPresent')
    clear_on_read_data_present.text = 'false'
    create_session_return.append(clear_on_read_data_present)

    create_session_response.append(create_session_return)
    return envelope_soap_body(create_session_response)


# This seems to be invoked when performing a stepup, or password is expired, or ... ? I think this is the "update"
# session, although WebSEAL will invoke a terminateSession and invoke createSession to "update" a session, so not sure.
def change_session(body):
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)
    session_id = body.find('{http://sms.am.tivoli.com}sessionID').text
    debug_message('sessionID: ' + session_id)
    session_limit = body.find('{http://sms.am.tivoli.com}sessionLimit').text
    debug_message('sessionLimit: ' + session_limit)

    # Loop over every 'data' credential attribute, and store it in Redis
    for data in body.findall('{http://sms.am.tivoli.com}data'):
        data_class = data.find('{http://sms.am.tivoli.com}dataClass').text
        # Store in Redis, this is based on session_id and 'data_class'
        redis_session_add_or_modify_attribute(session_id, data_class, data)

    # The rest is static values
    change_session_response = Element('ns1:changeSessionResponse')
    change_session_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    change_session_return = Element('ns1:changeSessionReturn')

    result = Element('ns1:result')
    result.text = '952467756'
    change_session_return.append(result)

    version = Element('ns1:version')
    version.text = '1'
    change_session_return.append(version)

    stack_depth = Element('ns1:stackDepth')
    stack_depth.text = '1'
    change_session_return.append(stack_depth)

    clear_on_read_data_present = Element('ns1:clearOnReadDataPresent')
    clear_on_read_data_present.text = 'false'
    change_session_return.append(clear_on_read_data_present)

    change_session_response.append(change_session_return)
    return envelope_soap_body(change_session_response)


def redis_create_session(replica_set, session_id):
    # Notify the replica_set:sessions key of the new session
    r.lpush(replica_set + ':sessions', session_id)


def redis_session_add_or_modify_attribute(session_id, data_class, session_data):
    # This adds credential data to the given attribute (or data_class)
    redis_key = session_id + ':' + data_class
    debug_message('adding redis session key: ' + redis_key)
    debug_message(tostring(session_data))
    r.set(redis_key, tostring(session_data))
    redis_session_keys = session_id + ':keys'
    r.lpush(redis_session_keys, data_class)


def get_session(body):
    debug_message(tostring(body))
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)
    session_id = body.find('{http://sms.am.tivoli.com}sessionID').text
    debug_message('sessionID: ' + session_id)
    sso_type = body.find('{http://sms.am.tivoli.com}ssoType').text
    debug_message('ssoType: ' + sso_type)
    sso_source = body.find('{http://sms.am.tivoli.com}ssoSource')
    # debug_message('ssoSource: ' + tostring(sso_source)) # this is sometimes None and doesn't seem important either

    get_session_response = Element('ns1:getSessionResponse')
    get_session_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    get_session_return = Element('ns1:getSessionReturn')

    result = Element('ns1:result')
    result.text = '952467768'
    get_session_return.append(result)

    version = Element('ns1:version')
    version.text = '0'
    get_session_return.append(version)

    # I verify whether the session id is in the replica set and whether or not it's still active
    if string_in_list(replica_set + ':sessions', session_id) and not is_session_inactive(replica_set, session_id):
        # Found an existing, active session
        redis_session_keys = session_id + ':keys'
        for i in range(0, r.llen(redis_session_keys)):
            # This is intermediary, it's unsafe to use decode() on a None
            redis_session_key_b = r.lindex(redis_session_keys, i)
            if redis_session_key_b is not None:
                # Not None, safe to continue
                redis_session_key = redis_session_key_b.decode('utf-8')
                # Get the data associated to the credential attribute, these are still bytes if they're not None
                session_data_b = r.get(session_id + ':' + redis_session_key)
                if session_data_b is not None:
                    # Convert to an XML document, you can't copy this straight to the response, for some reason the
                    # stored XML contains 'ns0', and WebSEAL doesn't appear happy with that.
                    # replace('ns0', 'ns1') doesn't seem to work either :(
                    session_data_xml = ET.fromstring(session_data_b.decode('utf-8'))
                    # Remove the change policy from response, it's not returned from vanilla DSC either
                    change_policy = session_data_xml.find('{http://sms.am.tivoli.com}changePolicy')
                    session_data_xml.remove(change_policy)

                    # Get the existing values
                    session_data_value = session_data_xml.find('{http://sms.am.tivoli.com}value')
                    session_data_data_class = session_data_xml.find('{http://sms.am.tivoli.com}dataClass')
                    session_data_instance = session_data_xml.find('{http://sms.am.tivoli.com}instance')

                    # Skeleton element for the data
                    return_data_xml = Element('ns1:data')

                    # Value is annoying, it sometimes contains an attribute, and sometimes actual text, so I check
                    # that here and set it accordingly
                    if session_data_value is not None and session_data_value.text is None:
                        return_data_xml = Element('ns1:data')
                        return_data_xml.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
                        ET.SubElement(return_data_xml, 'ns1:value', {'xsi:nil': 'true'})
                    else:
                        return_data_value = Element('ns1:value')
                        return_data_value.text = session_data_value.text
                        return_data_xml.append(return_data_value)

                    # Append the other attribute options as well
                    return_data_data_class = Element('ns1:dataClass')
                    return_data_data_class.text = session_data_data_class.text
                    return_data_xml.append(return_data_data_class)

                    return_data_instance = Element('ns1:instance')
                    return_data_instance.text = session_data_instance.text
                    return_data_xml.append(return_data_instance)

                    # Append the session attribute to the 'getSessionReturn' element.
                    get_session_return.append(return_data_xml)

    # Again, a static value
    stack_depth = Element('ns1:stackDepth')
    stack_depth.text = '1'
    get_session_return.append(stack_depth)

    # Append the 'getSessionReturn' to 'getSessionResponse'
    get_session_response.append(get_session_return)

    debug_message(tostring(get_session_response))
    return envelope_soap_body(get_session_response)


def idle_timeout(body):
    debug_message(tostring(body))
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)
    session_id = body.find('{http://sms.am.tivoli.com}sessionID').text
    debug_message('sessionID: ' + session_id)

    # This will mark a session as idle
    idle_session(replica_set, session_id)

    # Again, a static response
    idle_timeout_response = Element('ns1:idleTimeoutResponse')
    idle_timeout_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    idle_timeout_return = Element('ns1:idleTimeoutReturn')
    idle_timeout_return.text = '952467756'

    idle_timeout_response.append(idle_timeout_return)
    return envelope_soap_body(idle_timeout_response)


def idle_session(replica_set, session_id):
    redis_inactive_key = session_id + ':com.tivoli.am.eb.is-inactive'
    res = r.get(redis_inactive_key)
    session_data = ET.fromstring(res)
    debug_message(tostring(session_data))

    # Mark the session attribute as inactive
    session_data.find('{http://sms.am.tivoli.com}value').text = 'true'
    r.set(redis_inactive_key, tostring(session_data))


def is_session_inactive(replica_set, session_id):
    redis_inactive_key = session_id + ':com.tivoli.am.eb.is-inactive'
    res = r.get(redis_inactive_key)

    if res is None:
        # Session does not exist, so it's safe to say it's inactive.
        return True

    session_data_inactivity = ET.fromstring(res).find('{http://sms.am.tivoli.com}value').text

    if session_data_inactivity == 'true':
        # In case it's inactive, we remove it altogether and mark is inactive
        remove_session(replica_set, session_id)
        return True
    else:
        # Not inactive
        return False


def remove_session(replica_set, session_id):
    debug_message('removing session in replica_set ' + replica_set)
    # Remove the session id from the replica_set, e.g.: default:sessions
    rem = r.lrem(replica_set + ':sessions', 0, session_id)
    if rem > 0:
        # In case something was removed, attempt to remove all associated session attributes as well
        debug_message('removing session details of session id ' + session_id)
        redis_session_keys = session_id + ':keys'
        session_keys_len = r.llen(redis_session_keys)
        debug_message('There are ' + str(session_keys_len) + ' keys associated to the session_id.')

        redis_session_key_b = r.lpop(redis_session_keys)
        while redis_session_key_b is not None:
            # Get the key name as utf-8
            attribute_name = redis_session_key_b.decode('utf-8')
            # Construct the Redis session key name
            redis_session_key = session_id + ':' + attribute_name
            debug_message('deleting redis session key: ' + session_id + ':' + redis_session_key)
            # Delete the session key
            res = r.delete(session_id + ':' + redis_session_key)
            debug_message('result for deleting keys was: ' + str(res))
            # Pop to continue
            redis_session_key_b = r.lpop(redis_session_keys)
    else:
        debug_message('replica set had no associated sessions')


def terminate_session(body):
    debug_message(tostring(body))
    replica = body.find('{http://sms.am.tivoli.com}replica').text
    debug_message('replica: ' + replica)
    replica_set = body.find('{http://sms.am.tivoli.com}replicaSet').text
    debug_message('replicaSet: ' + replica_set)
    session_id = body.find('{http://sms.am.tivoli.com}sessionID').text
    debug_message('sessionID: ' + session_id)

    # Remove the session in Redis
    remove_session(replica_set, session_id)

    # The response is static
    terminate_session_response = Element('ns1:terminateSessionResponse')
    terminate_session_response.set('xmlns:ns1', "http://sms.am.tivoli.com")

    terminate_session_return = Element('ns1:terminateSessionReturn')

    result = Element('ns1:result')
    result.text = '952467756'
    terminate_session_return.append(result)

    version = Element('ns1:version')
    version.text = '0'
    terminate_session_return.append(version)

    stack_depth = Element('ns1:stackDepth')
    stack_depth.text = '0'
    terminate_session_return.append(stack_depth)

    clear_on_read_data_present = Element('ns1:clearOnReadDataPresent')
    clear_on_read_data_present.text = 'false'
    terminate_session_return.append(clear_on_read_data_present)

    terminate_session_response.append(terminate_session_return)
    return envelope_soap_body(terminate_session_response)


def envelope_soap_body(soap_body):
    envelope = Element('SOAP-ENV:Envelope')
    envelope.set('xmlns:SOAP-ENV', 'http://schemas.xmlsoap.org/soap/envelope/')
    envelope.set('xmlns:xsd', 'http://www.w3.org/2001/XMLSchema')
    envelope.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')

    body = Element('SOAP-ENV:Body')

    body.append(soap_body)
    envelope.append(body)
    return envelope


if __name__ == '__main__':
    # Not run when using gunicorn
    app.run(host='0.0.0.0')
