
import socket
import json

# esta función se encarga de recibir el mensaje completo desde el cliente
# en caso de que el mensaje sea más grande que el tamaño del buffer 'buff_size', esta función va esperar a que
# llegue el resto. Para saber si el mensaje ya llegó por completo, se busca el caracter de fin de mensaje (parte de nuestro protocolo inventado)

def receive_full_message(connection_socket, buff_size,middlechar):
    # recibimos la primera parte del mensaje
    recv_message = connection_socket.recv(buff_size)
    full_message = recv_message

    # verificamos si llegó el mensaje header completo o si aún faltan partes del mensaje
    separator = contains_message(full_message,middlechar)

    # entramos a un while para recibir el resto y seguimos esperando información
    # mientras el buffer no contenga secuencia de fin de mensaje
    while  separator==-1: 
        # recibimos un nuevo trozo del mensaje
        recv_message = connection_socket.recv(buff_size)

        # lo añadimos al mensaje "completo"
        full_message += recv_message

        # verificamos si es la última parte del mensaje
        separator = contains_message(full_message,middlechar)
    # finalmente retornamos el mensaje
    return full_message

#Esta funcion, se va a encargar de recibir  de que el proxy reciba el mensaje entero del servidor
def receive_full_messageV2(connection_socket,buff_size,middle_char):
    half_msje = receive_full_message(connection_socket,buff_size,middle_char)
    #ahora tenemos que recibir todo el mensaje html, para eso necesitamos el content-length
    index = contains_message(half_msje,middle_char) #hay que sumarle cuatro, dado que \r\n\r\n vale 4
    parsed_msje = parse_http_message(half_msje[:index+4])
    content_length = parsed_msje.get(b'Content-Length')
    rest_msje = half_msje[(index+4):]
    contador = int(content_length)-len(rest_msje)
    other_half = "".encode()
    #tenemos que seguir recibiendo el mensaje, hasta que se envien todos los bytes
    while(contador!=0):
        recv_message = connection_socket.recv(buff_size)
        other_half+=recv_message
        contador-=len(recv_message)
    final=other_half
    half_msje+=final
    #enviamos el mensaje decoded
    return half_msje


#Funcion que nos servira para ver la existencia de end_sequence en message
def contains_message(message, end_sequence):
    return message.find(end_sequence)

#reemplaza 
def replace_words(message,word,nword):
    segmented = message.split(word)
    newmessage=segmented[0]
    if(len(segmented)>1):
        newmessage+=nword
    for i in range(1,len(segmented)):
        newmessage+=segmented[i]+nword    
    return newmessage[:len(newmessage)-len(nword)]

#esta funcion recorre el mensaje,
def censored_words(message,forbidden):
    newmessage = ""
    la=forbidden['forbidden_words']
    el= []
    for i in la:
        for key, value in i.items():
            el.append((key,value))
    for word in el:
        key = word[0]
        nword = word[1]
        newmessage = replace_words(message,key,nword)
        message=newmessage
    print(f"este es el mensaje censurado:\n{newmessage}")    
    return newmessage
        
            



def start_server():  
  # definimos el tamaño del buffer de recepción y la secuencia de fin de mensaje
  buff_size = 87
  end_of_message = b"\r\n\r\n"
  new_socket_address = ('localhost', 8000)
  print("ingrese el nombre del archivo json\n")
  name_json = input()
  print("ingrese la ruta donde esta el archivo json\n")
  ubicacion_json = input()
  print("Abriendo el archivo json")
  with open(ubicacion_json+'/'+name_json) as json_file:
    jsondata = json.load(json_file)
    print('JSON file uploaded successfully')
  print('Creando socket - Servidor')
  # armamos el socket
  # los parámetros que recibe el socket indican el tipo de conexión
  # socket.SOCK_STREAM = socket orientado a conexión
  server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  
  # le indicamos al server socket que debe atender peticiones en la dirección address
  # para ello usamos bind
  server_socket.bind(new_socket_address)
  
  # luego con listen (función de sockets de python) le decimos que puede
  # tener hasta 3 peticiones de conexión encoladas
  # si recibiera una 4ta petición de conexión la va a rechazar
  server_socket.listen(3)
  
  # nos quedamos esperando a que llegue una petición de conexión
  print('... Esperando clientes')
  while True:
      # cuando llega una petición de conexión la aceptamos
      # y se crea un nuevo socket que se comunicará con el cliente
      new_socket, new_socket_address = server_socket.accept()
  
      # luego recibimos el mensaje usando la función que programamos
      # esta función entrega el mensaje en string (no en bytes) y con el end_of_message
      recv_message = receive_full_message(new_socket, buff_size, end_of_message)
      print(f' -> Se ha recibido el siguiente mensaje: {recv_message}\n')
      
      #en este paso tenemos que crear el nuevo socket, para poder conectarnos con el server
      #la dirección que queremos usar esta en el recv_message, en particular en el startline
      proxy_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      parse_request = parse_http_message(recv_message)
      #Del header host obtenemos la dirección a la cual queremos enviar la información
      ip = parse_request.get(b'Host').decode() 
      print(ip)
      sv_address = (ip.strip(),80)
      proxy_client.connect(sv_address)
      print(f"se conectó con el proxy exitosamente, usando la url {ip[1:]}\n")
      #tenemos que obtener la ip junto al formato, lo vamos a conseguir del startline
      print(f"este es el mensaje parseado {parse_request}")
      content_startline = parse_request.get(b'startline').split(b" ")
      uri = content_startline[1].decode() #webpage que estamos solicitando
      flag = False
      parse_request.setdefault(b'X-ElQuePregunta', b'Cristobal Suazo Ortiz' )
      for webpage in jsondata['blocked']:
          if (uri==webpage):
            flag = True 
      new_recv = create_http_message(parse_request)
      #aquí se envía el mensaje desde el proxy hacía el servidor
      proxy_client.send(new_recv)
      #se recibe el mensaje del servidor
      message_from_sv = receive_full_messageV2(proxy_client, buff_size,end_of_message)
      print(f' -> Respuesta del servidor:\n{message_from_sv}')
      #HTTP/1.1 200 OK, a priori asumimos que no hay errores
      parse_response=parse_http_message(message_from_sv)
      #verificamos si la página web está en el archivo json, i.e., es una página prohibida
      print(f"mensaje en dic del sv:\n{parse_response}")
      if(flag):
          #cambiar startline por el error
          parse_response.update({b'startline':content_startline[2]+b" 403 Forbidden"})
          parse_response.update({b'body':b'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>No tienes permiso para ver esta pagina :c</title>
</head>
<body>
    <h1>naonao error 403</h1>
</body>
</html>'''}) #quitamos el contenido del response
          parse_response.update({b'Content-Length':bytes(str(len(parse_response.get(b'body'))),'UTF-8') })     
      print(f"este es el msje parseado\n{parse_response}")    
      #final_message = create_http_message(parse_response)    
      proxy_client.close()
      #ahora tenemos que buscar palabras que deban ser censuradas, solo en caso de que no haya error
      if (not flag):
        censored_message = censored_words(parse_response.get(b'body').decode(),jsondata)
        parse_response.update({b'body':bytes(censored_message,'UTF-8')})
        parse_response.update({b'Content-Length':bytes(str(len(parse_response.get(b'body'))),'UTF-8')})
      print(f"este es el parse_response actualizado:\n{parse_response}")
      final_message = create_http_message(parse_response)
      print(f"este es el mensaje final:\n{final_message}")
      new_socket.send(final_message)
      print(f"se envió el siguiente mensaje hacía el cliente\n{final_message}")
      # cerramos la conexión
      new_socket.close()
      print(f"conexión con {new_socket_address} ha sido cerrada")
      # seguimos esperando por si llegan otras conexiones


'''
f: http_message -> diccionario
Función que recibe un mensaje http, y lo parsea, transformándolo en un diccionario
'''
def parse_http_message(http_message):
    #separamos el cuerpo de la cabeza
    head , body = http_message.split(b"\r\n\r\n")
    #ahora hacemos un split con \r\n
    headers = head.split(b"\r\n")
    #aquí separamos el start line, del resto de los headers
    st = headers[0]
    rest = headers[1:]
    #la idea ahora es generar un diccionario, st y body tendrán una key llamada: startline y body, respectivamente
    dic = {}
    dic.setdefault(b"startline", st)
    if (len(body)!=0): #en caso de que el body sea de length 0
        dic.setdefault(b"body",body)
    #ahora agregaremos los demas headers, pero antes crearemos tuplas, separadas por los : 
    for i in range(0,len(rest)):
        rest[i] = rest[i].split(b":")
    for i in range(0, len(rest)):
        #considerar casos donde hayan mas de dos puntos!!, porque solo nos importa el primero
        if (len(rest[i])>1):
            #hay que reconstruir el valor que nos dieron
            for t in range(2,len(rest[i])):
                rest[i][1]+=':'.encode()+rest[i][t]
        dic.setdefault(rest[i][0],rest[i][1])
    return dic
'''
f: diccionario -> http_message
A partir de un diccionario, tenemos que volver a crear un mensaje http
'''
def create_http_message(dic_http):
    #sabemos que siempre habrá un startline
    initstr =(dic_http.pop(b"startline")+b"\r\n") 
    print(f"este es el dic {dic_http}")
    #si el largo de los headers es 0, entonces el for no hará nada, por lo que no es necesario preocuparse
    #en el caso de que no hayan headers
    for i in dic_http:
        print(i)
        print(dic_http.get(i))
        if(i==b"body"):
            continue
        initstr+=(i+b':'+ dic_http.get(i)+b"\r\n")    
    initstr += b"\r\n\r\n" 
    if (dic_http.get(b"body")!=None):
        body = dic_http.pop(b"body")
        initstr+=body
    return initstr

if __name__ == '__main__':
    start_server()
    #TODO hacer el informe y los test!!!
    
