from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.contrib.auth.views import redirect_to_login
from django.template import loader, RequestContext
from django.utils import simplejson

from voting.models import Vote

def vote_on_object(request, model, post_vote_redirect=None,
        object_id=None, slug=None, slug_field=None, template_name=None,
        template_loader=loader, extra_context=None, context_processors=None,
        template_object_name='object', allow_xmlhttprequest=False):
        
    if allow_xmlhttprequest and request.is_ajax():
        return xmlhttprequest_vote_on_object(request, model,
                                             object_id=object_id, slug=slug,
                                             slug_field=slug_field)

    if extra_context is None: extra_context = {}

    try:
        vote = dict(VOTE_DIRECTIONS)[direction]
    except KeyError:
        raise AttributeError("'%s' is not a valid vote type." % vote_type)

    # Look up the object to be voted on
    lookup_kwargs = {}
    if object_id:
        lookup_kwargs['%s__exact' % model._meta.pk.name] = object_id
    elif slug and slug_field:
        lookup_kwargs['%s__exact' % slug_field] = slug
    else:
        raise AttributeError('Generic vote view must be called with either '
                             'object_id or slug and slug_field.')
    try:
        obj = model._default_manager.get(**lookup_kwargs)
    except ObjectDoesNotExist:
        raise Http404, 'No %s found for %s.' % (model._meta.app_label, lookup_kwargs)

    if request.method == 'POST':
        vote = int(request.POST.get('vote'))
        
        if post_vote_redirect is not None:
            next = post_vote_redirect
        elif request.REQUEST.has_key('next'):
            next = request.REQUEST['next']
        elif hasattr(obj, 'get_absolute_url'):
            if callable(getattr(obj, 'get_absolute_url')):
                next = obj.get_absolute_url()
            else:
                next = obj.get_absolute_url
        else:
            raise AttributeError('Generic vote view must be called with either '
                                 'post_vote_redirect, a "next" parameter in '
                                 'the request, or the object being voted on '
                                 'must define a get_absolute_url method or '
                                 'property.')
        Vote.objects.record_vote(obj, vote, request.META['REMOTE_ADDR'], request.user)
        return HttpResponseRedirect(next)
    else:
        if not template_name:
            template_name = '%s/%s_confirm_vote.html' % (
                model._meta.app_label, model._meta.object_name.lower())
        t = template_loader.get_template(template_name)
        c = RequestContext(request, {
            template_object_name: obj,
            'direction': direction,
        }, context_processors)
        for key, value in extra_context.items():
            if callable(value):
                c[key] = value()
            else:
                c[key] = value
        response = HttpResponse(t.render(c))
        return response

def json_error_response(error_message):
    return HttpResponse(simplejson.dumps(dict(success=False,
                                              error_message=error_message)))

def xmlhttprequest_vote_on_object(request, model,
    object_id=None, slug=None, slug_field=None):
    """
    Generic object vote function for use via XMLHttpRequest.

    Properties of the resulting JSON object:
        success
            ``true`` if the vote was successfully processed, ``false``
            otherwise.
        score
            The object's updated score and number of votes if the vote
            was successfully processed.
        error_message
            Contains an error message if the vote was not successfully
            processed.
    """
    if request.method == 'GET':
        return json_error_response(
            'XMLHttpRequest votes can only be made using POST.')
    
    try:
        vote = int(request.POST.get('vote'))
    except KeyError:
        return json_error_response(
            '\'%s\' is not a valid vote type.' % direction)

    # Look up the object to be voted on
    lookup_kwargs = {}
    if object_id:
        lookup_kwargs['%s__exact' % model._meta.pk.name] = object_id
    elif slug and slug_field:
        lookup_kwargs['%s__exact' % slug_field] = slug
    else:
        return json_error_response('Generic XMLHttpRequest vote view must be '
                                   'called with either object_id or slug and '
                                   'slug_field.')
    try:
        obj = model._default_manager.get(**lookup_kwargs)
    except ObjectDoesNotExist:
        return json_error_response(
            'No %s found for %s.' % (model._meta.verbose_name, lookup_kwargs))

    # Vote and respond
    changed = Vote.objects.record_vote(obj, vote, request.META['REMOTE_ADDR'], request.user)

    return HttpResponse(simplejson.dumps({
        'success': True,
        'changed': changed,
        'score': Vote.objects.get_score(obj),
    }))
