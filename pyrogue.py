#!/usr/bin/python3

import tcod as tcod, math, textwrap

# FOV constants
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

MAX_ROOM_MONSTERS = 3
# size of window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# size of map
MAP_WIDTH = 80
MAP_HEIGHT = 45

# sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

# message bar constants
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
# create the list of game messages and their colors, starts empty
game_msgs = []

LIMIT_FPS = 20 # 20 frames per second maximum

color_dark_wall = tcod.Color(0, 0, 100)
color_light_wall = tcod.Color(130, 110, 50)
color_dark_ground = tcod.Color(50, 50, 150)
color_light_ground = tcod.Color(200, 180, 50)

font_path = 'arial10x10.png'
font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD

window_title = 'pyrogue'
fullscreen = False

player_x = SCREEN_WIDTH // 2
player_y = SCREEN_HEIGHT // 2

ROOM_MAX_SIZE = 10 
ROOM_MIN_SIZE = 6 
MAX_ROOMS = 30

class Rect:
	#a rectangle on the map. use to characterize a room.
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h

	def center(self):
		center_x = (self.x1 + self.x2) // 2
		center_y = (self.y1 + self.y2) // 2
		return (center_x, center_y)

	def intersect(self, other):
		#returns true if this rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			self.y1 <= other.y2 and self.y2 >= other.y1)
			
class Tile:
	# a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		self.explored = False

		# by default, if a tile is blocked, it also blocks sight
		####### Try to understand this later ########
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Object:
	# this is a generic object: the player, a monster, an item, the stairs, etc.
	# it's always represented by a character on the screen.
	def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None):
		self.name = name
		self.blocks = blocks
		self.x = x
		self.y = y
		self.char = char
		self.color = color

		self.fighter = fighter
		if self.fighter:   # let the fighter component know who owns it
			self.fighter.owner = self

		self.ai = ai
		if self.ai:   # let the AI component know who owns it
			self.ai.owner = self

	def move(self, dx, dy):
		# move by the given amount, if the destination is not blocked
		#if not map[self.x + dx][self.y + dy].blocked:
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def move_towards(self, target_x, target_y):
		# vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		#normalize it to length 1 (preserving direction), then round it and
		#conver to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)

	def draw(self):
		if tcod.map_is_in_fov(fov_map, self.x, self.y):    # check fov before drawing
			# set the color and then draw the character that represented this object at its position
			tcod.console_set_default_foreground(con, self.color)
			tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

	def clear(self):
		# erase the character that represents this object
		tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)

	def distance_to(self, other):
		#return the ditance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
	
	def send_to_back(self):
		# make this object be drawn first, so all others appear above it if they're in the same tile
		global objects
		objects.remove(self)
		objects.insert(0, self)

class Fighter:
	#combat-related properties and methods (monster, player, NPC)
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function

	def take_damage(self, damage):
		# apply damage if possible
		if damage > 0:
			self.hp -= damage
		# check for death. if there's a death function, call it
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)

	def attack(self, target):
		# a simple formula for attack damage
		damage = self.power - target.fighter.defense

		if damage > 0:
			# make the target take some damage
			print(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			print("%s attacks %s but it has no effect!" % (self.owner.name.capitalize(), target.name))

class BasicMonster:
	#AI for a basic monster
	def take_turn(self):
		# a basic monster takes its turn. If you can see it, it can see you.
		monster = self.owner
		if tcod.map_is_in_fov(fov_map, monster.x, monster.y):
			# move towards the player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)

			# close enough, attack! (if the player is still alive)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

def create_room(room):
	global map
	# go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False

def make_map():
	global map

	# fill map with "blocked" tiles
	map = [
		[Tile(True) for y in range(MAP_HEIGHT)]
		for x in range (MAP_WIDTH)
	]

	rooms = []
	num_rooms = 0

	for r in range(MAX_ROOMS):
		#random width and height
		w = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#random position without going out of the boundaries of the map
		x = tcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = tcod.random_get_int(0, 0, MAP_HEIGHT- h - 1)
		
		#Rect class makes rectangles easier to work with
		new_room = Rect(x, y, w, h)

		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break

		if not failed:
			#this means there are no intersections, so this room is valid

			#"paint" it to the map's tiles
			create_room(new_room)

			#center coordinate of the new room, will be useful later
			(new_x, new_y) = new_room.center()

			if num_rooms == 0:
				#this is the first room, where the player starts at
				player.x = new_x
				player.y = new_y

			else:
				#all roms after the first:
				#connect it to the previous room with a tunnel

				#center coordinate of the previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()

				#flip a coint (random number that is either 0 or 1)
				if tcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically, then horizontally
					create_v_tunnel(prev_y, new_y, new_x)
					create_h_tunnel(prev_x, new_x, new_y)

			place_objects(new_room)
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1


def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
	global map
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_light_ground, color_dark_ground
	global fov_recompute

	if fov_recompute:
		# recomputer FOV is needed (the player moved or something)
		fov_recompute = False
		tcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		# go through all the tiles, and set their background color
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = tcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					# if it's not visible right now, the player can only see it if its explored
					if map[x][y].explored:
						#it's out of players fov
						if wall:
							tcod.console_set_char_background(con, x, y, color_dark_wall, tcod.BKGND_SET)
						else:
							tcod.console_set_char_background(con, x, y, color_dark_ground, tcod.BKGND_SET)
				else:
					#it's visible
					if wall:
						tcod.console_set_char_background(con, x, y, color_light_wall, tcod.BKGND_SET)
					else:
						tcod.console_set_char_background(con, x, y, color_light_ground, tcod.BKGND_SET)
					# since it's visible, explore it
					map[x][y].explored = True

	# draw all objects in the list, except the player.
	# we want it to always appear over all other objects! so its drawn later
	for object in objects:
		if object != player:
			object.draw()
	player.draw()

	# blit the contents of "con" to the root console and present it
	tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

	# prepare to render the GUI panel
	tcod.console_set_default_background(panel, tcod.black)
	tcod.console_clear(panel)

	# show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, tcod.light_red, tcod.darker_red)

	# blit the contents of "panel" to the root console
	tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)


def handle_keys():
	# key = tcod.console_check_for_keypress() # Real time
	key = tcod.console_wait_for_keypress(True)
	if key.vk == tcod.KEY_ENTER and key.lalt:
		#Alt+Enter fullscreen
		tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
	elif key.vk == tcod.KEY_ESCAPE:
		return 'exit' #exit game
	global player_x, player_y
	
	if game_state == 'playing':
		# movement keys
		if tcod.console_is_key_pressed(tcod.KEY_UP):
			player_move_or_attack(0, -1)
			fov_recompute = True
		elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
			player_move_or_attack(0, 1)
			fov_recompute = True
		elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
			player_move_or_attack(-1, 0)
			fov_recompute = True
		elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
			player_move_or_attack(1, 0)
			fov_recompute = True
	else:
		return 'didnt-take-turn'

def place_objects(room):
	#choose random number of monsters
	num_monsters = tcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

	for i in range(num_monsters):
		# choose random spot for this monster
		x = tcod.random_get_int(0, room.x1, room.x2)
		y = tcod.random_get_int(0, room.y1, room.y2)

		if not is_blocked(x, y):
			if tcod.random_get_int(0, 0, 100) < 80:  # 80% chance of orc
				#create an orc
				fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
				ai_component = BasicMonster()

				monster = Object(x, y, 'o', 'orc', tcod.desaturated_green,
					blocks=True,fighter=fighter_component, ai=ai_component)
			else:
				# create a troll
				fighter_component = Fighter(hp=16, defense=1, power=4)
				ai_component = BasicMonster()

				monster = Object(x, y, 'T', 'troll', tcod.darker_green,
					blocks=True,fighter=fighter_component, ai=ai_component)

			objects.append(monster)

def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True

	# now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def player_move_or_attack(dx, dy):
	global fov_recompute

	# the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy

	# try to find an attackable object there
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	
	# attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx,dy)
		fov_recompute = True

def player_death(player):
	#the game ended!
	global game_state
	print('You died!')
	game_state = 'dead'

	#for added effect, transform player into a corpse!
	player.char = '%'
	player.color = tcod.dark_red

def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be attacked and doesn't move
	print(monster.name.capitalize() + ' is dead!')
	monster.char = '%'
	monster.color = tcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc.) first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)

	#render the background first
	tcod.console_set_default_background(panel, back_color)
	tcod.console_rect(panel, x, y, total_width, 1, False, tcod.BKGND_SCREEN)

	#now render the bar on top
	tcod.console_rect(panel, x, y, bar_width, 1, False, tcod.BKGND_SCREEN)
	if bar_width > 0:
		tcod.console_rect(panel, x, y, bar_width, 1, False, tcod.BKGND_SCREEN)
	
	#finally, some centered text with the values
	tcod.console_set_default_foreground(panel, tcod.white)
	tcod.console_print_ex(panel, int(x + total_width / 2), y, tcod.BKGND_NONE, tcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def message(new_msg, color = tcod.white):
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]

		#add the new line as a tuple, with text and the color
		game_msgs.append( (line, color) )
	
	#print the game messages, one line at a time
	y = 1
	for (line, color) in game_msgs:
		tcod.console_set_default_foreground(panel, color)
		tcod.console_print_ex(panel, MSG_X, y, tcod.BKGND_NONE, tcod.LEFT, line)
		y += 1

game_state = 'playing'
player_action = None

#########################################
# Initialization & Main Loop
#########################################

tcod.console_set_custom_font(font_path, font_flags)
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT,window_title, fullscreen)
tcod.sys_set_fps(LIMIT_FPS)
con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = tcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

# create object representing player
fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)

# the list of objects
objects = [player]

#generate map (at this point it's not drawn to the screen)
make_map()

# create the FOV map, according to the generated map
fov_map = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
	for x in range (MAP_WIDTH):
		tcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

fov_recompute = True
game_state = 'playing'
player_action = None

# warm welcoming message!
message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', tcod.red)
while not tcod.console_is_window_closed():

	# render the screen
	render_all()

	tcod.console_flush()

	#erase all objects at their old locations, before they move
	for object in objects:
		object.clear()

	# handle keys and exit game if needed
	player_action = handle_keys()
	if player_action == 'exit':
		break

	# let monsters take their turn
	if game_state == 'playing' and player_action != 'didnt-take-turn':
		for object in objects:
			if object.ai:
				object.ai.take_turn()
