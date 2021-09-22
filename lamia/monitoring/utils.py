def apply_pagination(q, qp, model):
    if not qp: return q
    if 'order' in qp:
        orderBy = getattr(model, qp['order']) 
        if 'sort' in qp:
            if qp['sort'] == 'asc':
                #q = q.order_by(f"{qp['order']} asc")
                q = q.order_by(orderBy.asc())
            elif qp['sort'] == 'desc':  #< todo?
                #q = q.order_by(f"{qp['order']} desc")
                q = q.order_by(orderBy.desc())
            else:
                return {'errors': f"`sort' is \"{qp['sort']}\" (`desc', `asc' are only allowed)."}
        else:
            #q = q.order_by(f"{qp['order']} asc")
            q = q.order_by(orderBy.desc())
        #q.order_by()
    nTotal = q.count()
    if 'limit' in qp:
        q = q.limit(qp['limit'])
    if 'offset' in qp:
        q = q.offset(qp['offset'])
    return q, nTotal
